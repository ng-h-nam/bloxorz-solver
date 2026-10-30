"""
File kiểm tra riêng cho Replayer, PlayerDataManager, Tính điểm & BackgroundSolverWorker.

Cách chạy:
  1. Chạy toàn bộ bộ kiểm thử tự động (Unit Test):
     python test_replayer.py
  2. Chạy thử nghiệm trực quan trên cửa sổ 3D (tự động giải bằng AI và phát Replay):
     python test_replayer.py --gui
     python test_replayer.py --gui --stage 8
"""

import argparse
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.game import Game  # noqa: E402
from core.map_loader import load_coolmath_stage  # noqa: E402
from tests.gui.test_gui_integration import TestReplayerAndSolverIntegration  # noqa: E402


def run_visual_demo(stage_num: int = 1) -> None:
    """Mở cửa sổ 3D ở màn `stage_num` và tự động kích hoạt Solver + Replayer."""
    from gui.window import Window

    board = load_coolmath_stage(stage_num)
    game = Game(board)
    win = Window(game, level_name=board.name)
    win.run_solver()
    win.run()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kiểm tra riêng mô-đun Replayer, Tính điểm, Tài khoản & Background Solver."
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Mở trực tiếp cửa sổ 3D và tự động chạy Giải AI + Phát lại Replay.",
    )
    parser.add_argument(
        "--stage",
        type=int,
        default=1,
        help="Số thứ tự màn chơi (1..33) khi chạy với --gui (mặc định: 1).",
    )
    args, remaining = parser.parse_known_args()

    if args.gui:
        run_visual_demo(stage_num=args.stage)
        return

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestReplayerAndSolverIntegration)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    main()
