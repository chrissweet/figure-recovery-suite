"""Section 1 gate: calibration round-trip + categorical-x snap."""

import json

from cv_oracle.calibration import Calibration, snap_categorical_x


def test_roundtrip_within_tolerance(el94):
    """pixel -> data -> pixel must return the original pixel within <1px."""
    cal = Calibration.from_calibration_file(el94["calibration"])
    fb = cal.plot_frame_box
    for col in range(fb["left"], fb["right"], 50):
        for row in range(fb["top"], fb["bottom"], 50):
            x, y = cal.pixel_to_data(col, row)
            col2, row2 = cal.data_to_pixel(x, y)
            assert abs(col2 - col) < 1e-6
            assert abs(row2 - row) < 1e-6


def test_worked_example_matches_calibration_json(el94):
    """The worked example baked into calibration.json must reproduce."""
    cal_dict = json.load(open(el94["calibration"]))
    cal = Calibration.from_calibration_json(cal_dict)
    we = cal_dict["worked_example"]
    col, row = cal.data_to_pixel(we["input"]["x"], we["input"]["y"])
    assert round(col) == we["result"]["col"]
    assert round(row) == we["result"]["row"]


def test_log_axis_roundtrip():
    """A log-y axis must round-trip a decade span exactly."""
    from cv_oracle.calibration import Axis

    # value = 10 ** (m*row + b); pick m,b so row 0 -> 1.0, row 100 -> 1000.
    ax = Axis(m=3.0 / 100.0, b=0.0, log=True)
    assert abs(ax.to_data(0) - 1.0) < 1e-9
    assert abs(ax.to_data(100) - 1000.0) < 1e-6
    assert abs(ax.to_pixel(ax.to_data(57)) - 57) < 1e-9


def test_categorical_snap_fixes_bar_drift():
    """el-62/el-80 drift {23.34, 26.33, 29.34} must snap to {24, 27, 30}."""
    ticks = [24, 27, 30]
    assert snap_categorical_x(23.34, ticks) == 24
    assert snap_categorical_x(26.33, ticks) == 27
    assert snap_categorical_x(29.34, ticks) == 30


def test_categorical_snap_leaves_genuine_offtick_alone():
    """A value beyond half-group width of every tick is left unchanged."""
    ticks = [24, 27, 30]  # spacing 3 -> snap zone is +/-1.5 around each tick
    assert snap_categorical_x(35.0, ticks) == 35.0  # 5.0 from nearest (30) -> kept
    assert snap_categorical_x(20.0, ticks) == 20.0  # 4.0 from nearest (24) -> kept
    # tighter control: a value 2.0 from the nearest tick is outside the zone.
    assert snap_categorical_x(22.0, ticks) == 22.0
