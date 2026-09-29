"""Tests for the TUI's pure rendering functions and watch evaluator."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from chip8.cpu import Chip8
from chip8.schip import SuperChip8
from chip8.tui import (
    UiState, WatchError, eval_watch, format_breakpoints, format_disasm,
    format_mem, format_regs, format_stack, format_watches, layout,
    render_frame, status_line,
)


def make_cpu():
    c = Chip8()
    c.load_rom(bytes([0x61, 0x05, 0x62, 0x0A, 0x81, 0x24, 0x12, 0x06]))
    c.v[1] = 5
    c.v[2] = 10
    c.v[4] = 0x24
    c.i = 0x300
    c.delay = 7
    c.sound = 3
    c.stack = [0x202, 0x30A]
    return c


def test_format_regs_exact():
    c = make_cpu()
    lines = format_regs(c)
    assert lines[0] == "V0=00 V1=05 V2=0A V3=00"
    assert lines[1] == "V4=24 V5=00 V6=00 V7=00"
    assert lines[2] == "V8=00 V9=00 VA=00 VB=00"
    assert lines[3] == "VC=00 VD=00 VE=00 VF=00"
    assert lines[4] == "I=300 PC=0200 DT=07 ST=03"
    assert lines[5] == "SP=2"


def test_format_disasm_marks_pc_and_breakpoints():
    c = make_cpu()
    lines = format_disasm(c, {0x202}, before=1, after=1)
    assert len(lines) == 3
    assert lines[0] == "> 0200: 6105  LD V1, 0x05"
    assert lines[1] == " *0202: 620A  LD V2, 0x0a"
    assert lines[2] == "  0204: 8124  ADD V1, V2"


def test_format_disasm_uses_schip_mnemonics():
    c = SuperChip8()
    c.load_rom(bytes([0x00, 0xFF, 0x00, 0xFB]))
    lines = format_disasm(c, set(), before=0, after=1)
    assert lines[0] == "> 0200: 00FF  HIGH"
    assert lines[1] == "  0202: 00FB  SCR"


def test_format_stack():
    c = make_cpu()
    assert format_stack(c) == ["0: 030A", "1: 0202"]
    c.stack = []
    assert format_stack(c) == ["(empty)"]


def test_format_mem_exact():
    c = make_cpu()
    for i in range(8):
        c.memory[0x300 + i] = i * 17  # 0, 17, 34, 51, 68, 85, 102, 119
    lines = format_mem(c, 0x300, rows=1)
    assert lines[0] == "0300: 00 11 22 33 44 55 66 77 |..\"3DUfw|"


def test_format_mem_ascii_gutter():
    c = make_cpu()
    c.memory[0x200:0x208] = b"Hi\x00\xffbye!"
    lines = format_mem(c, 0x200, rows=1)
    assert lines[0] == "0200: 48 69 00 FF 62 79 65 21 |Hi..bye!|"


def test_format_breakpoints_sorted():
    assert format_breakpoints({0x300, 0x200}) == ["0200", "0300"]
    assert format_breakpoints(set()) == ["(none)"]


def test_format_watches_values_and_errors():
    c = make_cpu()
    lines = format_watches(c, ["V1 + V2", "bogus + 1"])
    assert lines[0] == "V1 + V2 = 15 (0xf)"
    assert lines[1].startswith("bogus + 1 = <err:")
    assert format_watches(c, []) == ["(none)"]


def test_eval_watch_registers_and_specials():
    c = make_cpu()
    assert eval_watch(c, "V1") == 5
    assert eval_watch(c, "VF") == 0
    assert eval_watch(c, "I") == 0x300
    assert eval_watch(c, "PC") == 0x200
    assert eval_watch(c, "DT") == 7
    assert eval_watch(c, "ST") == 3
    assert eval_watch(c, "SP") == 2


def test_eval_watch_arithmetic_and_precedence():
    c = make_cpu()
    assert eval_watch(c, "V1 + V2 * 2") == 25      # mul binds tighter
    assert eval_watch(c, "(V1 + V2) * 2") == 30
    assert eval_watch(c, "0x10 + 8") == 24
    assert eval_watch(c, "V2 - V1") == 5
    assert eval_watch(c, "V4 / 4") == 9
    assert eval_watch(c, "V4 % 7") == 1
    assert eval_watch(c, "V4 & 0x0F") == 4
    assert eval_watch(c, "V1 | V2") == 15
    assert eval_watch(c, "V1 ^ V2") == 15
    assert eval_watch(c, "V1 << 3") == 40
    assert eval_watch(c, "V4 >> 2") == 9
    assert eval_watch(c, "-V1 + 10") == 5
    assert eval_watch(c, "~0 & 0xFF") == 255


def test_eval_watch_errors():
    c = make_cpu()
    for bad in ["", "V16", "QQ", "V1 +", "(V1", "V1 / 0", "V1 % 0",
                "V1 5", "@"]:
        try:
            eval_watch(c, bad)
        except WatchError:
            continue
        raise AssertionError(f"no error for {bad!r}")


def test_layout_panes_exact():
    panes = layout(100, 30)
    assert panes["disasm"] == (0, 0, 63, 20)
    assert panes["regs"] == (64, 0, 36, 7)
    assert panes["stack"] == (64, 7, 36, 6)
    assert panes["mem"] == (0, 20, 100, 10)
    assert panes["status"] == (0, 29, 100, 1)
    # watches + breakpoints tile the space between stack and mem
    wx, wy, ww, wh = panes["watches"]
    bx, by, bw, bh = panes["breakpoints"]
    assert (wx, ww) == (64, 36)
    assert wy == 13 and by == wy + wh and by + bh == 20


def test_layout_clamps_tiny_terminals():
    panes = layout(10, 5)
    for name, (x, y, w, h) in panes.items():
        assert w > 0 and h > 0, name
    assert panes["mem"][3] == 10


def test_layout_no_pane_exceeds_screen():
    for w, h in [(80, 24), (120, 40), (70, 24)]:
        cw, ch = max(w, 70), max(h, 28)  # layout clamps to a minimum
        for name, (x, y, pw, ph) in layout(w, h).items():
            assert x + pw <= cw, (name, w)
            assert y + ph <= ch, (name, h)


def test_render_frame_clips_to_panes():
    c = make_cpu()
    ui = UiState()
    ui.watches = ["V1", "V2", "I", "PC", "DT", "ST", "SP", "V3+V4"]
    frame, panes = render_frame(c, ui, 100, 30)
    assert set(frame) == {"disasm", "regs", "stack", "watches",
                          "breakpoints", "mem", "status"}
    for name, lines in frame.items():
        _, _, pw, ph = panes[name]
        assert len(lines) <= ph, name
        assert all(len(line) <= pw for line in lines), name
    assert frame["regs"][0].startswith("V0=00")
    assert frame["status"][0].startswith("chip8 pc=0200")


def test_status_line_modes():
    c = make_cpu()
    ui = UiState()
    ui.breakpoints.add(0x300)
    assert "chip8" in status_line(c, ui)
    assert "bps=1" in status_line(c, ui)
    s = SuperChip8()
    assert status_line(s, UiState()).startswith("schip")


def test_ui_state_defaults():
    ui = UiState()
    assert ui.breakpoints == set()
    assert ui.watches == []
    assert ui.mem_addr == 0x200
    assert ui.running is False
