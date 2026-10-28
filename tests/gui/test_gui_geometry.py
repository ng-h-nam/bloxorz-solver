import math

from core.block import Direction
from core.map_loader import parse_level
from core.state import Orientation, State
from core.transition import SINGLE_CUBE_DELTA, TRANSITION_TABLE
from gui.shared.geometry import (
    DEFAULT_FACE_SHADE,
    FACE_NORMALS,
    ROLL_AXIS,
    active_piece,
    block_bounds,
    block_pieces,
    broken_fragile_cell,
    cube_bounds,
    roll_face_shades,
    roll_pivot,
    rotated_face_shades,
)


def rotate(point, axis, degrees):
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    x, y, z = point
    d = axis[0] * x + axis[1] * y + axis[2] * z
    cross = (
        axis[1] * z - axis[2] * y,
        axis[2] * x - axis[0] * z,
        axis[0] * y - axis[1] * x,
    )
    return tuple(
        p * c + cross[i] * s + axis[i] * d * (1 - c) for i, p in enumerate((x, y, z))
    )


def rolled_bounds(bounds, direction):
    px, pz, axis, sign = roll_pivot(bounds, direction)
    x0, x1, y0, y1, z0, z1 = bounds
    moved = [
        rotate((x - px, y, z - pz), axis, sign * 90)
        for x in (x0, x1)
        for y in (y0, y1)
        for z in (z0, z1)
    ]
    moved = [(x + px, y, z + pz) for x, y, z in moved]
    return tuple(
        round(v, 6)
        for v in (
            min(p[0] for p in moved),
            max(p[0] for p in moved),
            min(p[1] for p in moved),
            max(p[1] for p in moved),
            min(p[2] for p in moved),
            max(p[2] for p in moved),
        )
    )


def test_all_twelve_rolls_land_on_new_bounds():
    for (orientation, direction), (dr, dc, new_orientation) in TRANSITION_TABLE.items():
        old = State(5, 5, orientation)
        new = State(5 + dr, 5 + dc, new_orientation)
        assert rolled_bounds(block_bounds(old), direction) == tuple(
            float(v) for v in block_bounds(new)
        ), (orientation, direction)


def test_single_cube_rolls_land_on_neighbour_cell():
    for direction, (dr, dc) in SINGLE_CUBE_DELTA.items():
        direction = Direction[direction] if isinstance(direction, str) else direction
        assert rolled_bounds(cube_bounds(5, 5), direction) == tuple(
            float(v) for v in cube_bounds(5 + dr, 5 + dc)
        ), direction


def test_pieces_for_whole_and_split_block():
    whole = State(3, 4, Orientation.HORIZONTAL)
    assert block_pieces(whole) == [block_bounds(whole)]
    assert active_piece(whole) == 0
    split = State(2, 2, Orientation.SPLIT, frozenset(), (2, 6), 1)
    assert block_pieces(split) == [cube_bounds(2, 2), cube_bounds(2, 6)]
    assert active_piece(split) == 1


def axis_name(vector):
    """Tên mặt (trong hệ thế giới) mà một vector đơn vị trùng với, hoặc None nếu không nằm trên trục."""
    for name, normal in FACE_NORMALS.items():
        if all(abs(a - b) < 1e-9 for a, b in zip(vector, normal)):
            return name
    return None


def test_shades_at_rest_are_exactly_the_table():
    for direction in ROLL_AXIS:
        assert (
            roll_face_shades(DEFAULT_FACE_SHADE, direction, 0.0) == DEFAULT_FACE_SHADE
        )


def test_shades_after_a_ninety_degree_roll_match_the_table_in_the_new_position():
    """Cuối cú lăn, mặt đã xoay tới hướng nào thì sáng đúng như mặt tĩnh ở hướng đó: không còn nhảy."""
    for direction, (axis, sign) in ROLL_AXIS.items():
        shades = roll_face_shades(DEFAULT_FACE_SHADE, direction, 90.0)
        for name, normal in FACE_NORMALS.items():
            rotated = rotate(normal, axis, sign * 90.0)
            world = axis_name(tuple(round(v, 9) for v in rotated))
            assert world is not None
            assert abs(shades[name] - DEFAULT_FACE_SHADE[world]) < 1e-9, (
                direction,
                name,
                world,
            )


def test_shades_change_smoothly_while_rolling_and_falling():
    for direction in ROLL_AXIS:
        previous = roll_face_shades(DEFAULT_FACE_SHADE, direction, 0.0)
        for degree in range(1, 151):  # cả pha lăn (0 đến 90) lẫn pha rơi (đến 150)
            current = roll_face_shades(DEFAULT_FACE_SHADE, direction, float(degree))
            for name in FACE_NORMALS:
                assert abs(current[name] - previous[name]) < 0.02, (
                    direction,
                    name,
                    degree,
                )
            previous = current


def test_shades_stay_inside_the_table_range():
    low, high = min(DEFAULT_FACE_SHADE.values()), max(DEFAULT_FACE_SHADE.values())
    for direction in ROLL_AXIS:
        for degree in range(0, 361, 5):
            for value in roll_face_shades(
                DEFAULT_FACE_SHADE, direction, float(degree)
            ).values():
                assert low - 1e-9 <= value <= high + 1e-9


def test_tilt_about_any_axis_is_also_continuous():
    for degree in range(1, 30):
        a = rotated_face_shades(DEFAULT_FACE_SHADE, (1.0, 0.0, 0.0), float(degree - 1))
        b = rotated_face_shades(DEFAULT_FACE_SHADE, (1.0, 0.0, 0.0), float(degree))
        assert all(abs(a[n] - b[n]) < 0.02 for n in FACE_NORMALS)


def test_broken_fragile_cell_only_when_standing_on_a_fragile_tile():
    board = parse_level(
        ["S.-.H", "....."]
    )  # cú pháp coolmath: "." là sàn, "-" là ô giòn, "H" là đích
    assert broken_fragile_cell(board, State(0, 2, Orientation.STANDING)) == (0, 2)
    assert (
        broken_fragile_cell(board, State(0, 2, Orientation.HORIZONTAL)) is None
    )  # nằm thì an toàn
    assert (
        broken_fragile_cell(board, State(0, 1, Orientation.STANDING)) is None
    )  # sàn thường
    assert (
        broken_fragile_cell(board, State(7, 2, Orientation.STANDING)) is None
    )  # ngoài bản đồ
    split = State(0, 2, Orientation.SPLIT, frozenset(), (1, 2), 0)
    assert broken_fragile_cell(board, split) is None  # khối đơn không làm vỡ ô
