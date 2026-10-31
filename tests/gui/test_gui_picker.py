from gui.model.level_picker import MAX_VISIBLE_ROWS, LevelPicker


def test_open_selects_current_and_scrolls_it_into_view():
    picker = LevelPicker([f"m{i}" for i in range(40)])
    picker.open(30)
    start, end = picker.visible_range()
    assert picker.selected == 30 and start <= 30 < end and end - start == MAX_VISIBLE_ROWS


def test_move_and_page_clamp_at_both_ends():
    picker = LevelPicker([f"m{i}" for i in range(40)])
    picker.open(0)
    picker.move(-5)
    assert picker.selected == 0
    picker.page(1)
    assert picker.selected == MAX_VISIBLE_ROWS - 1
    picker.move(1000)
    assert picker.selected == 39 and picker.visible_range()[1] == 40


def test_few_levels_show_only_what_exists():
    picker = LevelPicker(["a", "b", "c"])
    picker.open(1)
    _, rows = picker.layout(1280, 768)
    assert len(rows) == 3 and picker.visible_range() == (0, 3)


def test_row_at_returns_global_index_even_when_scrolled():
    picker = LevelPicker([f"m{i}" for i in range(40)])
    picker.open(35)
    box, rows = picker.layout(1280, 768)
    start, _ = picker.visible_range()
    for i, rect in enumerate(rows):
        assert picker.row_at(rect.center, 1280, 768) == start + i
    assert picker.row_at((0, 0), 1280, 768) is None
    assert picker.box_contains(box.center, 1280, 768) and not picker.box_contains((0, 0), 1280, 768)


def test_scroll_by_stays_in_range():
    picker = LevelPicker([f"m{i}" for i in range(20)])
    picker.open(0)
    picker.scroll_by(100)
    assert picker.scroll == 20 - MAX_VISIBLE_ROWS
    picker.scroll_by(-100)
    assert picker.scroll == 0
