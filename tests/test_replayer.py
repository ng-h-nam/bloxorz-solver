import os
import sys
import tempfile
import unittest
from pathlib import Path

import pygame

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from algorithms.bfs import BFSSolver  # noqa: E402
from algorithms.dfs import DFSSolver  # noqa: E402
from core.block import Direction  # noqa: E402
from core.game import Game, GameStatus  # noqa: E402
from core.map_loader import load_coolmath_stage  # noqa: E402
from core.state import State, state_key  # noqa: E402
from gui.animator import Animator  # noqa: E402
from gui.passcode_prompt import char_from_key  # noqa: E402
from gui.replayer import (  # noqa: E402
    AccountPrompt,
    BackgroundSolverWorker,
    PlayerDataManager,
    Replayer,
    calculate_level_score,
    verify_solver_state_key,
)
from gui.window import discover_available_solvers  # noqa: E402


class TestReplayerAndSolverIntegration(unittest.TestCase):
    """
    Bộ kiểm thử toàn diện cho gui/replayer.py và tích hợp GUI:
      1. Rà soát khóa trạng thái của solver (verify_solver_state_key) gồm cầu và tách khối.
      2. Quản lý tài khoản, tính điểm dựa trên số bước đi (calculate_level_score)
         và lưu/đọc dữ liệu người chơi (PlayerDataManager).
      3. Hộp thoại tài khoản (AccountPrompt) và xử lý phím nhập liệu (char_from_key).
      4. Replayer phát lại đúng đường đi (Stage 01 cơ bản & Stage 08 tách/gộp khối + SWITCH),
         đồng bộ chuẩn với core.game.Game và gui.animator.Animator.
      5. Replayer phát hiện đường đi không hợp lệ (rơi khối).
      6. Chạy solver nền (BackgroundSolverWorker) với BFS, DFS cùng hàng đợi kết quả (result_queue)
         và hàng đợi lỗi (error_queue).
    """

    def test_01_verify_solver_state_key_bridges_and_split(self):
        """Kiểm tra hàm rà soát khóa trạng thái phát hiện đúng cả state_key chuẩn và hàm lỗi."""
        ok, issues = verify_solver_state_key(state_key)
        self.assertTrue(ok)
        self.assertEqual(issues, [])

        # Kiểm tra tương thích với BaseSolver.get_state_key (BFS & DFS)
        stage_01 = load_coolmath_stage(1)
        bfs = BFSSolver(stage_01)
        dfs = DFSSolver(stage_01)
        ok_bfs, issues_bfs = verify_solver_state_key(bfs.get_state_key)
        ok_dfs, issues_dfs = verify_solver_state_key(dfs.get_state_key)
        self.assertTrue(ok_bfs)
        self.assertEqual(issues_bfs, [])
        self.assertTrue(ok_dfs)
        self.assertEqual(issues_dfs, [])

        # Giả lập một hàm khóa trạng thái thiếu cầu và tách khối -> phải bị phát hiện lỗi
        def broken_key(s: State):
            return (s.r, s.c, s.orientation)

        ok_bad, issues_bad = verify_solver_state_key(broken_key)
        self.assertFalse(ok_bad)
        self.assertGreaterEqual(len(issues_bad), 3)

    def test_02_player_data_manager_save_and_load_replay(self):
        """Kiểm tra đăng ký, đăng nhập, tính điểm theo số bước và lưu/tải dữ liệu Replay."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "players.json"
            manager = PlayerDataManager(storage_path=json_path)

            ok, _ = manager.authenticate_or_register("phong", "123456")
            self.assertTrue(ok)
            self.assertEqual(manager.current_user, "phong")

            # Lưu lịch sử từ game.move_history (chứa cả Direction enum và chuỗi 'SWITCH')
            moves_first = [
                Direction.RIGHT,
                Direction.RIGHT,
                "SWITCH",
                Direction.DOWN,
                Direction.LEFT,
            ]
            manager.record_game_session("Stage 08", moves_first, won=True, mode="MANUAL", elapsed_time=6.4)
            self.assertEqual(manager.get_level_score_info("Stage 08")["score"], 4)

            # Lượt chơi tốt hơn (3 bước < 4 bước) -> Kỷ lục phải được cập nhật xuống 3 bước
            moves_better = [Direction.RIGHT, Direction.RIGHT, "SWITCH", Direction.DOWN]
            manager.record_game_session("Stage 08", moves_better, won=True, mode="MANUAL", elapsed_time=5.2)

            saved = manager.get_saved_replay("Stage 08")
            self.assertEqual(saved, ["RIGHT", "RIGHT", "SWITCH", "DOWN"])
            profile = manager.get_current_profile()
            self.assertIsNotNone(profile)
            # Điểm chỉ dựa duy nhất trên số bước đi (base_level_score = move_count = 3)
            self.assertEqual(calculate_level_score(move_count=3, won=True), 3)
            self.assertEqual(calculate_level_score(move_count=10, won=False), 0)
            self.assertEqual(profile.best_scores["Stage 08"], 3)
            self.assertEqual(profile.best_times["Stage 08"], 5.2)

            score_info = manager.get_level_score_info("Stage 08")
            self.assertIsNotNone(score_info)
            self.assertEqual(score_info["score"], 3)
            self.assertEqual(score_info["move_count"], 3)
            self.assertEqual(score_info["elapsed_time"], 5.2)

            # Kiểm tra đăng xuất và đọc lại từ đĩa
            manager.logout()
            self.assertIsNone(manager.current_user)

            manager_reloaded = PlayerDataManager(storage_path=json_path)
            ok_login, _ = manager_reloaded.authenticate_or_register("phong", "123456")
            self.assertTrue(ok_login)
            self.assertEqual(
                manager_reloaded.get_saved_replay("Stage 08"),
                ["RIGHT", "RIGHT", "SWITCH", "DOWN"],
            )

    def test_03_account_prompt_and_key_input(self):
        """Kiểm tra hộp thoại AccountPrompt và hàm đọc ký tự bàn phím char_from_key."""
        prompt = AccountPrompt()
        prompt.open(current_user="guest")
        self.assertTrue(prompt.is_open)
        self.assertEqual(prompt.active_field, 0)

        for ch in "player_1":
            prompt.type_char(ch)
        self.assertEqual(prompt.username, "player_1")

        prompt.switch_field()
        self.assertEqual(prompt.active_field, 1)
        for ch in "secret9":
            prompt.type_char(ch)
        prompt.backspace()
        self.assertEqual(prompt.password, "secret")

        self.assertEqual(char_from_key(pygame.K_a, "", shift=False), "a")
        self.assertEqual(char_from_key(pygame.K_a, "", shift=True), "A")
        self.assertEqual(char_from_key(pygame.K_5, "5", shift=False), "5")
        self.assertEqual(char_from_key(pygame.K_MINUS, "", shift=True), "_")

        prompt.close()
        self.assertFalse(prompt.is_open)
        self.assertEqual(prompt.password, "")

    def test_04_replayer_stage_01_and_stage_08_split_merge(self):
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

        # Tua từng bước tiến / lùi và kiểm tra đồng bộ với Game + Animator
        replayer_01.step_forward()
        self.assertEqual(replayer_01.current_index, 1)
        self.assertEqual(game_01.moves, 1)
        self.assertTrue(animator.active)
        animator.cancel()

        replayer_01.step_backward()
        self.assertEqual(replayer_01.current_index, 0)
        self.assertEqual(game_01.moves, 0)

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

    def test_05_replayer_detects_invalid_path(self):
        """Kiểm tra Replayer phát hiện chính xác bước đi làm rơi khối xuống vực."""
        stage_01 = load_coolmath_stage(1)
        replayer = Replayer(stage_01, ["UP", "UP"])
        self.assertFalse(replayer.is_valid_path)
        self.assertFalse(replayer.reaches_goal)
        self.assertIn("không hợp lệ", replayer.error_message)
        self.assertEqual(replayer.timeline[-1].status, GameStatus.LOST)

    def test_06_background_solver_worker_and_error_queue(self):
        """Kiểm tra chạy Solver nền (BFS & DFS) và xử lý hàng đợi lỗi (error_queue)."""
        solvers = dict(discover_available_solvers())
        self.assertIn("BFS", solvers)
        self.assertIn("DFS", solvers)

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

        # 2. Chạy DFSSolver(stage_01) trên luồng nền
        dfs_solver = DFSSolver(stage_01)
        worker.start_solver(dfs_solver, algorithm_name="DFS")
        worker.join(timeout=5.0)
        res_dfs, err_dfs = worker.poll_events()
        self.assertEqual(err_dfs, [])
        self.assertIsNotNone(res_dfs)
        self.assertTrue(res_dfs.is_solved)
        self.assertGreater(len(res_dfs.actions), 0)

        # 3. Kiểm tra bắt ngoại lệ vào error_queue khi Solver gặp lỗi
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
