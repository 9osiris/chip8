"""Tests for the Super-CHIP 1.1 extensions: hires mode, scrolling,
16x16 sprites, the large font, RPL flags, and the new disassembler."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from chip8.schip import (
    SuperChip8, HIRES_W, HIRES_H, LORES_W, LORES_H,
    LARGE_FONTSET, LARGE_FONT_START,
    disassemble_schip, is_schip_op,
)


def step(*words, cpu=None, v=None, mem=None, cycles=1):
    c = cpu or SuperChip8()
    out = bytearray()
    for w in words:
        out += bytes([w >> 8, w & 0xFF])
    c.load_rom(out)
    for i, val in (v or {}).items():
        c.v[i] = val
    for a, val in (mem or {}).items():
        c.memory[a] = val
    for _ in range(cycles):
        c.cycle()
    return c


def lit_pixels(c):
    return {(x, y) for y in range(HIRES_H) for x in range(HIRES_W)
            if c.display[y * HIRES_W + x]}


def test_high_low_switch_modes():
    c = step(0x00FF)
    assert c.hires and (c.dw, c.dh) == (128, 64)
    c.pc = 0x200
    c.load_rom(bytes([0x00, 0xFE]))
    c.cycle()
    assert not c.hires and (c.dw, c.dh) == (64, 32)


def test_lores_draw_uses_top_left_quadrant():
    # 1x1 sprite at (63, 31) lands at the corner of the quadrant
    c = step(0xA300, 0x6000, 0x6100, 0xD011,
             mem={0x300: 0x80}, cycles=4)
    assert c.pixel(0, 0) == 1
    assert c.pixel(64, 0) == 0  # outside the quadrant stays dark
    assert c.pixel(0, 32) == 0


def test_hires_draw_uses_full_buffer():
    c = step(0x00FF, 0xA300, 0x6040, 0x6120, 0xD011,
             mem={0x300: 0x80}, cycles=5)
    assert c.pixel(0x40, 0x20) == 1
    assert c.v[0xF] == 0


def test_hires_draw_wraps_at_128x64():
    c = step(0x00FF, 0xA300, 0x607F, 0x613F, 0xD011,
             mem={0x300: 0xC0}, cycles=5)
    # sprite at (127, 63), two pixels wide: second pixel wraps to x=0
    assert c.pixel(127, 63) == 1
    assert c.pixel(0, 63) == 1


def test_dxy0_hires_draws_16x16():
    # 16x16 checkerboard-ish sprite: first two rows all set
    sprite = [0xFF, 0xFF, 0xFF, 0xFF] + [0x00] * 28
    mem = {0x300 + i: b for i, b in enumerate(sprite)}
    c = step(0x00FF, 0xA300, 0x6005, 0x6103, 0xD010,
             mem=mem, cycles=5)
    assert c.pixel(5, 3) == 1
    assert c.pixel(20, 3) == 1   # x + 15
    assert c.pixel(5, 4) == 1    # second row
    assert c.pixel(5, 5) == 0    # third row is empty
    assert c.pixel(21, 3) == 0   # x + 16 is outside the sprite
    assert c.v[0xF] == 0


def test_dxy0_hires_collision_sets_vf():
    sprite = [0xFF, 0xFF] + [0x00] * 30
    mem = {0x300 + i: b for i, b in enumerate(sprite)}
    c = step(0x00FF, 0xA300, 0x6000, 0x6100, 0xD010,
             mem=mem, cycles=5)
    assert c.v[0xF] == 0
    c.pc = 0x208  # draw again at the same spot
    c.cycle()
    assert c.v[0xF] == 1
    assert c.pixel(0, 0) == 0  # xor erased


def test_dxy0_lores_draws_half_size():
    # 16x16 sprite, all bits set in the top-left 2x2 block only
    sprite = [0xC0, 0x00, 0xC0, 0x00] + [0x00] * 28
    mem = {0x300 + i: b for i, b in enumerate(sprite)}
    c = step(0xA300, 0x600A, 0x6106, 0xD010,
             mem=mem, cycles=4)
    assert not c.hires
    # the 2x2 block at sprite (0..1, 0..1) becomes one pixel at (10, 6)
    assert c.pixel(10, 6) == 1
    # neighbors that would be lit at full size stay dark
    assert c.pixel(11, 6) == 0
    assert c.pixel(10, 7) == 0
    assert c.pixel(12, 6) == 0


def test_scroll_down_moves_pixels():
    c = step(0xA300, 0x6000, 0x6100, 0xD011, 0x00C2,
             mem={0x300: 0x80}, cycles=5)
    assert c.pixel(0, 0) == 0   # old spot cleared
    assert c.pixel(0, 2) == 1   # moved down 2
    assert c.pc == 0x20A


def test_scroll_down_drops_pixels_off_bottom():
    c = step(0xA300, 0x601E, 0x611F, 0xD011, 0x00C4,
             mem={0x300: 0xC0}, cycles=5)
    # pixels at (30, 31) and (31, 31) scrolled down 4: gone
    assert c.pixel(30, 31) == 0
    assert c.pixel(31, 31) == 0
    assert sum(c.display) == 0


def test_scroll_right_and_left():
    c = step(0xA300, 0x6000, 0x6105, 0xD011, 0x00FB,
             mem={0x300: 0x80}, cycles=5)
    assert c.pixel(0, 5) == 0
    assert c.pixel(4, 5) == 1
    c.pc = 0x200  # run a fresh 00FC
    c.load_rom(bytes([0x00, 0xFC]))
    c.cycle()
    assert c.pixel(4, 5) == 0
    assert c.pixel(0, 5) == 1


def test_scroll_in_hires_moves_full_region():
    c = step(0x00FF, 0xA300, 0x6070, 0x6100, 0xD011, 0x00FB,
             mem={0x300: 0x80}, cycles=6)
    assert c.pixel(0x70, 0) == 0
    assert c.pixel(0x74, 0) == 1  # x=112 + 4


def test_exit_sets_flag_and_freezes():
    c = step(0x00FD, 0x6001)
    assert c.exited
    assert c.pc == 0x202
    c.cycle()
    c.cycle()
    assert c.pc == 0x202  # frozen, the LD V0,1 never runs
    assert c.v[0] == 0


def test_fx30_points_at_large_font():
    c = step(0xF330, v={3: 0xB}, cycles=1)
    assert c.i == LARGE_FONT_START + 0xB * 10
    assert c.memory[c.i:c.i + 10] == bytes(LARGE_FONTSET[0xB * 10:0xB * 10 + 10])


def test_fx30_glyph_b_draws_with_drw_10():
    # draw the large B glyph (index 11) with a 10-row sprite
    c = step(0xFB30, 0x6000, 0x6100, 0xD01A, v={0xB: 0xB}, cycles=4)
    glyph = LARGE_FONTSET[0xB * 10:0xB * 10 + 10]
    for row, bits in enumerate(glyph):
        for col in range(8):
            want = 1 if bits & (0x80 >> col) else 0
            assert c.pixel(col, row) == want, f"mismatch at ({col}, {row})"


def test_fx75_fx85_roundtrip_rpl_flags():
    c = step(0xF275, 0x6000, 0x6100, 0xF285,
             v={0: 11, 1: 22, 2: 33}, cycles=4)
    assert c.rpl[:3] == [11, 22, 33]
    assert (c.v[0], c.v[1], c.v[2]) == (11, 22, 33)


def test_fx75_fx85_clamp_to_eight_flags():
    c = step(0xFF75, 0x60AA, 0xFF85, v={i: i + 1 for i in range(16)},
             cycles=3)
    assert c.rpl == [1, 2, 3, 4, 5, 6, 7, 8]
    assert list(c.v[:8]) == [1, 2, 3, 4, 5, 6, 7, 8]


def test_base_opcodes_still_work_in_schip():
    # the kat program from test_kats, minus the halt spin check
    words = [0x6005, 0x6107, 0x8014, 0xA300, 0xF255, 0x6000, 0xF265]
    c = step(*words, cycles=7)
    assert c.v[0] == 12
    assert c.memory[0x300] == 12
    assert c.v[1] == 7


def test_disassemble_schip_mnemonics():
    cases = {
        0x00C4: "SCD 4",
        0x00FB: "SCR",
        0x00FC: "SCL",
        0x00FD: "EXIT",
        0x00FE: "LOW",
        0x00FF: "HIGH",
        0xD120: "DRW V1, V2, 16",
        0xF330: "LD HF, V3",
        0xF575: "LD RPL, V5",
        0xF685: "LD V6, RPL",
        0x00E0: "CLS",
        0x61FF: "LD V1, 0xff",
    }
    for op, want in cases.items():
        assert disassemble_schip(op) == want, f"{op:#06x}"


def test_is_schip_op():
    assert is_schip_op(0x00C4)
    assert is_schip_op(0x00FB)
    assert is_schip_op(0x00FD)
    assert is_schip_op(0xD120)
    assert is_schip_op(0xF330)
    assert is_schip_op(0xF575)
    assert is_schip_op(0xF685)
    assert not is_schip_op(0x00E0)
    assert not is_schip_op(0xD125)
    assert not is_schip_op(0xF355)
