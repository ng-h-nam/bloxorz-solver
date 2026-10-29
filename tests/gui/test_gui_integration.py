"""Kiểm thử tích hợp (map thật, solver thật) cho phát lại, giải nền, tài khoản và khóa trạng thái.

Chuyển từ tests/test_replayer.py cũ sang API mới: Replayer(game, actions, ...) không còn nhận animator
(hoạt cảnh nhận qua on_step), BackgroundSolverWorker.start(solver, tên), discover_available_solvers() trả về SolverSpec.
"""

import sys
import tempfile
import unittest
from pathlib import Path

import pygame

PROJECT_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "core").is_dir())
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.bfs import BFSSolver
from algorithms.dfs import DFSSolver
from core.block import Direction
from core.game import Game, GameStatus
from core.map_loader import load_coolmath_stage
from core.state import State, state_key
from gui.engine.replay import Replayer, ReplayFrame
from gui.engine.solver_service import discover_available_solvers
from gui.engine.solver_worker import BackgroundSolverWorker, verify_solver_state_key
from gui.model.account_prompt import AccountPrompt
from gui.model.passcode_prompt import char_from_key
from gui.model.player_data import PlayerDataManager, calculate_level_score


class FailingSolver:
    """Solver giả luôn ném ngoại lệ trong luồng nền."""

    def solve(self) -> None:
        raise ValueError("Lỗi mô phỏng trong luồng Solver")


class TestReplayerAndSolverIntegration(unittest.TestCase):
    """
    Kiểm thử tích hợp cho phát lại và giải nền:
      1. Khóa trạng thái của solver thật (BFS, DFS) qua verify_solver_state_key.
      2. Tài khoản, điểm theo số bước, lưu và đọc lại đường đi tốt nhất (PlayerDataManager).
      3. Hộp thoại tài khoản (AccountPrompt) và đọc phím (char_from_key).
      4. Replayer phát lại đúng đường đi thắng ở Stage 01 và Stage 08 (tách, gộp khối và SWITCH).
      5. Replayer phát hiện đường đi không hợp lệ (rơi khối).
      6. Giải nền (BackgroundSolverWorker) với BFS, DFS thật và bắt lỗi của solver hỏng.
    """

    def test_01_verify_solver_state_key_bridges_and_split(self):
        """Khóa trạng thái chuẩn và của solver thật đạt kiểm tra; hàm khóa thiếu cầu và khối tách bị phát hiện."""
        ok, issues = verify_solver_state_key(state_key)
        self.assertTrue(ok)
        self.assertEqual(issues, [])

        stage_01 = load_coolmath_stage(1)
        for solver in (BFSSolver(stage_01), DFSSolver(stage_01)):
            ok_solver, issues_solver = verify_solver_state_key(solver.get_state_key)
            self.assertTrue(ok_solver, issues_solver)
            self.assertEqual(issues_solver, [])

        def broken_key(s: State):
            return (s.r, s.c, s.orientation)

        ok_bad, issues_bad = verify_solver_state_key(broken_key)
        self.assertFalse(ok_bad)
        self.assertGreaterEqual(len(issues_bad), 3)

    def test_02_player_data_manager_save_and_load_replay(self):
        """Đăng ký, đăng nhập, tính điểm theo số bước (không tính SWITCH) và lưu, tải đường đi."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "players.json"
            manager = PlayerDataManager(storage_path=json_path)

            ok, _ = manager.authenticate_or_register("phong", "123456")
            self.assertTrue(ok)
            self.assertEqual(manager.current_user, "phong")

            # game.move_history chứa cả Direction và chuỗi 'SWITCH'
            moves_first = [
                Direction.RIGHT,
                Direction.RIGHT,
                "SWITCH",
                Direction.DOWN,
                Direction.LEFT,
            ]
            manager.record_game_session("Stage 08", moves_first, won=True, mode="MANUAL", elapsed_time=6.4)
            self.assertEqual(manager.get_level_score_info("Stage 08")["score"], 4)

            # Lượt tốt hơn (3 bước < 4 bước) thì kỷ lục phải cập nhật xuống 3 bước
            moves_better = [Direction.RIGHT, Direction.RIGHT, "SWITCH", Direction.DOWN]
            manager.record_game_session("Stage 08", moves_better, won=True, mode="MANUAL", elapsed_time=5.2)

            self.assertEqual(
                manager.get_saved_replay("Stage 08"),
                ["RIGHT", "RIGHT", "SWITCH", "DOWN"],
            )
            profile = manager.get_current_profile()
            self.assertIsNotNone(profile)
            self.assertEqual(calculate_level_score(move_count=3, won=True), 3)
            self.assertEqual(calculate_level_score(move_count=10, won=False), 0)
            self.assertEqual(profile.best_scores["Stage 08"], 3)
            self.assertEqual(profile.best_times["Stage 08"], 5.2)

            score_info = manager.get_level_score_info("Stage 08")
            self.assertIsNotNone(score_info)
            self.assertEqual(score_info["score"], 3)
            self.assertEqual(score_info["move_count"], 3)
            self.assertEqual(score_info["elapsed_time"], 5.2)

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
        """Hộp thoại AccountPrompt và hàm đọc ký tự bàn phím char_from_key."""
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
        """Replayer phát lại chuẩn xác đường đi thắng ở Stage 01 và Stage 08 (có tách khối và SWITCH)."""
        stage_01 = load_coolmath_stage(1)
        bfs_res = BFSSolver(stage_01).solve()
        self.assertTrue(bfs_res.is_solved)

        game_01 = Game(stage_01)
        shown: list[tuple[int, bool]] = []

        def on_step(frame: ReplayFrame, animate: bool) -> None:
            shown.append((frame.step_index, animate))

        replayer_01 = Replayer(game_01, bfs_res.actions, step_interval=0.1, on_step=on_step)
        self.assertTrue(replayer_01.is_valid_path)
        self.assertTrue(replayer_01.reaches_goal)
        self.assertEqual(replayer_01.total_steps, 7)
        self.assertEqual(game_01.moves, 0)  # tạo Replayer chưa đụng tới ván

        # Tiến, lùi từng bước: đồng bộ với Game, và bước tiến yêu cầu hoạt cảnh (animate=True)
        replayer_01.step_forward()
        self.assertEqual(replayer_01.current_index, 1)
        self.assertEqual(game_01.moves, 1)
        self.assertEqual(shown[-1], (1, True))

        replayer_01.step_backward()
        self.assertEqual(replayer_01.current_index, 0)
        self.assertEqual(game_01.moves, 0)
        self.assertEqual(shown[-1], (0, False))  # lùi thì nhảy thẳng, không hoạt cảnh

        replayer_01.replay_all_to_end()
        self.assertTrue(replayer_01.is_finished)
        self.assertTrue(game_01.is_won())
        self.assertEqual(game_01.moves, 7)
        self.assertEqual(game_01.state, replayer_01.current_state)

        # Stage 08: cổng tách khối, lệnh SWITCH (viết là SPACE) và gộp khối
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
        replayer_08 = Replayer(Game(stage_08), solution_08, step_interval=0.05)
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
        # 13 hành động nhưng có 1 SWITCH nên chỉ 12 bước lăn vật lý
        self.assertEqual(replayer_08.game.moves, 12)

    def test_05_replayer_detects_invalid_path(self):
        """Replayer phát hiện chính xác bước đi làm rơi khối và không đụng tới ván."""
        game = Game(load_coolmath_stage(1))
        replayer = Replayer(game, ["UP", "UP"])
        self.assertFalse(replayer.is_valid_path)
        self.assertFalse(replayer.reaches_goal)
        self.assertIn("không hợp lệ", replayer.error_message)
        self.assertEqual(replayer.timeline[-1].status, GameStatus.LOST)
        self.assertEqual(game.moves, 0)

    def test_06_background_solver_worker_and_error_queue(self):
        """Giải nền với BFS, DFS thật và bắt ngoại lệ của solver hỏng thành sự kiện lỗi."""
        solvers = {spec.name: spec for spec in discover_available_solvers()}
        self.assertIn("BFS", solvers)
        self.assertIn("DFS", solvers)

        stage_01 = load_coolmath_stage(1)
        worker = BackgroundSolverWorker(audit_state_keys=True)

        run_id = worker.start(BFSSolver(stage_01), algorithm_name="BFS")
        self.assertIsNotNone(run_id)
        worker.join(timeout=5.0)

        res_event, err_events = worker.poll_events()
        self.assertEqual(err_events, [])
        self.assertIsNotNone(res_event)
        self.assertTrue(res_event.is_solved)
        self.assertEqual(len(res_event.actions), 7)
        self.assertGreater(res_event.expanded_nodes, 0)
        self.assertGreaterEqual(res_event.memory_peak_kb, 0.0)

        worker.start(DFSSolver(stage_01), algorithm_name="DFS")
        worker.join(timeout=5.0)
        res_dfs, err_dfs = worker.poll_events()
        self.assertEqual(err_dfs, [])
        self.assertIsNotNone(res_dfs)
        self.assertTrue(res_dfs.is_solved)
        self.assertGreater(len(res_dfs.actions), 0)

        worker.start(FailingSolver(), algorithm_name="BROKEN_SOLVER")
        worker.join(timeout=5.0)
        res_event_2, err_events_2 = worker.poll_events()
        self.assertIsNone(res_event_2)
        self.assertEqual(len(err_events_2), 1)
        self.assertEqual(err_events_2[0].error_type, "ValueError")
        self.assertIn("Lỗi mô phỏng", err_events_2[0].error_message)

    def test_07_architecture_fixes_board_and_transition(self):
        """
        Kiểm tra 2 mục cải tiến kiến trúc ở core:
          1. Board: có goal_pos (bí danh end_pos); khai báo name và passcode trong __init__.
          2. core/transition.py: đã loại bỏ biến toàn cục _CURRENT_BOARD.
        """
        import core.transition as transition_mod

        stage_01 = load_coolmath_stage(1)
        self.assertEqual(stage_01.goal_pos, stage_01.end_pos)
        self.assertEqual(stage_01.name, "Stage 01")
        self.assertEqual(stage_01.passcode, "780464")

        self.assertFalse(hasattr(transition_mod, "_CURRENT_BOARD"))
        self.assertFalse(hasattr(transition_mod, "set_active_board"))


if __name__ == "__main__":
    unittest.main()
