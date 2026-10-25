import tempfile
import unittest
from pathlib import Path

from algorithms.bfs import BFSSolver
from core.block import Direction
from core.game import Game, GameStatus
from core.map_loader import load_coolmath_stage
from core.state import State, state_key
from gui.animator import Animator
from gui.replayer import (
    BackgroundSolverWorker,
    PlayerDataManager,
    Replayer,
    verify_solver_state_key,
)


class TestReplayerAndSolverIntegration(unittest.TestCase):
    """
    Bộ kiểm thử toàn diện cho gui/replayer.py theo yêu cầu nhiệm vụ G2:
      1. Rà soát khóa trạng thái của solver (verify_solver_state_key) gồm cầu và tách khối.
      2. Lưu dữ liệu người chơi (PlayerDataManager: đăng ký, đăng nhập, lưu/đọc replay).
      3. Replayer phát lại đúng đường đi (Stage 01 cơ bản & Stage 08 tách/gộp khối + SWITCH),
         đồng bộ chuẩn với core.game.Game và gui.animator.Animator.
      4. Chạy solver nền (BackgroundSolverWorker) cùng hàng đợi kết quả (result_queue)
         và hàng đợi lỗi (error_queue).
    """

    def test_01_verify_solver_state_key_bridges_and_split(self):
        """Kiểm tra hàm rà soát khóa trạng thái phát hiện đúng cả state_key chuẩn và hàm lỗi."""
        ok, issues = verify_solver_state_key(state_key)
        self.assertTrue(ok)
        self.assertEqual(issues, [])

        # Kiểm tra tương thích với BaseSolver.get_state_key
        stage_01 = load_coolmath_stage(1)
        bfs = BFSSolver(stage_01)
        ok_solver, issues_solver = verify_solver_state_key(bfs.get_state_key)
        self.assertTrue(ok_solver)
        self.assertEqual(issues_solver, [])

        # Giả lập một hàm khóa trạng thái thiếu cầu và tách khối -> phải bị phát hiện lỗi
        def broken_key(s: State):
            return (s.r, s.c, s.orientation)

        ok_bad, issues_bad = verify_solver_state_key(broken_key)
        self.assertFalse(ok_bad)
        self.assertGreaterEqual(len(issues_bad), 3)

    def test_02_player_data_manager_save_and_load_replay(self):
        """Kiểm tra đăng ký, đăng nhập và lưu/tải dữ liệu Replay của người chơi."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "players.json"
            manager = PlayerDataManager(storage_path=json_path)

            ok, _ = manager.register("phong", "123456")
            self.assertTrue(ok)
            self.assertEqual(manager.current_user, "phong")

            # Lưu lịch sử từ game.move_history (chứa cả Direction enum và chuỗi 'SWITCH')
            moves = [Direction.RIGHT, Direction.RIGHT, "SWITCH", Direction.DOWN]
            manager.record_game_session("Stage 08", moves, won=True, mode="MANUAL", elapsed_time=5.2)

            saved = manager.get_saved_replay("Stage 08")
            self.assertEqual(saved, ["RIGHT", "RIGHT", "SWITCH", "DOWN"])
            profile = manager.get_current_profile()
            self.assertIsNotNone(profile)
            # 'SWITCH' không tính vào số bước lăn vật lý
            self.assertEqual(profile.best_scores["Stage 08"], 3)

            # Kiểm tra đọc lại từ đĩa
            manager_reloaded = PlayerDataManager(storage_path=json_path)
            ok_login, _ = manager_reloaded.login("phong", "123456")
            self.assertTrue(ok_login)
            self.assertEqual(
                manager_reloaded.get_saved_replay("Stage 08"),
                ["RIGHT", "RIGHT", "SWITCH", "DOWN"],
            )

    def test_03_replayer_stage_01_and_stage_08_split_merge(self):
        """Kiểm tra Replayer phát lại chuẩn xác đường đi thắng trên Stage 01 và Stage 08 (có tách khối)."""
        stage_01 = load_coolmath_stage(1)
        bfs_res = BFSSolver(stage_01).solve()
        self.assertTrue(bfs_res.is_solved)

        game_01 = Game(stage_01)
        animator = Animator()
        replayer_01 = Replayer(game_01, bfs_res.actions, step_interval=0.1, animator=animator)

        self.assertTrue(replayer_01.is_valid_path)
        self.assertTrue(replayer_01.reaches_goal)
        self.assertEqual(replayer_01.total_steps, 7)

        # Tua từng bước và kiểm tra đồng bộ với Game + Animator
        replayer_01.step_forward()
        self.assertEqual(replayer_01.current_index, 1)
        self.assertEqual(game_01.moves, 1)
        self.assertTrue(animator.active)
        animator.cancel()

        replayer_01.replay_all_to_end()
        self.assertTrue(replayer_01.is_finished)
        self.assertTrue(game_01.is_won())
        self.assertEqual(game_01.moves, 7)
        self.assertEqual(game_01.block.to_state(game_01.state.active_bridges), replayer_01.current_state)

        # Kiểm tra Stage 08 với cổng tách khối T, lệnh SWITCH và gộp khối
        stage_08 = load_coolmath_stage(8)
        solution_08 = [
            "RIGHT",
            "RIGHT",
            "DOWN",
            "DOWN",
            "DOWN",
            "RIGHT",
            "RIGHT",
            "SPACE",
            "UP",
            "UP",
            "UP",
            "RIGHT",
            "RIGHT",
        ]
        replayer_08 = Replayer(stage_08, solution_08, step_interval=0.05)
        self.assertTrue(replayer_08.is_valid_path)
        self.assertTrue(replayer_08.reaches_goal)

        replayer_08.play()
        steps_advanced = 0
        for _ in range(30):
            if replayer_08.update(0.05):
                steps_advanced += 1
            if replayer_08.is_finished:
                break

        self.assertEqual(steps_advanced, len(solution_08))
        self.assertEqual(replayer_08.game.status, GameStatus.WON)
        # 13 hành động tổng cộng nhưng có 1 hành động SPACE/SWITCH -> 12 bước lăn vật lý
        self.assertEqual(replayer_08.game.moves, 12)

    def test_04_replayer_detects_invalid_path(self):
        """Kiểm tra Replayer phát hiện chính xác bước đi làm rơi khối xuống vực."""
        stage_01 = load_coolmath_stage(1)
        replayer = Replayer(stage_01, ["UP", "UP"])
        self.assertFalse(replayer.is_valid_path)
        self.assertFalse(replayer.reaches_goal)
        self.assertIn("không hợp lệ", replayer.error_message)
        self.assertEqual(replayer.timeline[-1].status, GameStatus.LOST)

    def test_05_background_solver_worker_and_error_queue(self):
        """Kiểm tra chạy Solver nền (thread) và xử lý hàng đợi lỗi (error_queue)."""
        stage_01 = load_coolmath_stage(1)
        worker = BackgroundSolverWorker(check_state_key_before_run=True)

        # 1. Truyền trực tiếp đối tượng BFSSolver(stage_01)
        solver = BFSSolver(stage_01)
        started = worker.start_solver(solver, algorithm_name="BFS")
        self.assertTrue(started)
        worker.join(timeout=5.0)

        res_event, err_events = worker.poll_events()
        self.assertEqual(err_events, [])
        self.assertIsNotNone(res_event)
        self.assertTrue(res_event.is_solved)
        self.assertEqual(len(res_event.actions), 7)
        self.assertGreater(res_event.expanded_nodes, 0)
        self.assertGreaterEqual(res_event.memory_peak_kb, 0.0)

        # 2. Kiểm tra bắt ngoại lệ vào error_queue khi Solver gặp lỗi
        def failing_solver():
            raise ValueError("Lỗi mô phỏng trong luồng Solver")

        worker.start_solver(failing_solver, algorithm_name="BROKEN_SOLVER")
        worker.join(timeout=5.0)
        res_event_2, err_events_2 = worker.poll_events()
        self.assertIsNone(res_event_2)
        self.assertEqual(len(err_events_2), 1)
        self.assertEqual(err_events_2[0].error_type, "ValueError")
        self.assertIn("Lỗi mô phỏng", err_events_2[0].error_message)


if __name__ == "__main__":
    unittest.main()
