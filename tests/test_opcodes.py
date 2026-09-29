"""Per-opcode unit tests for the CHIP-8 cpu."""

import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from chip8.cpu import Chip8


def step(*words, v=None, keys=None, mem=None, delay=None, cycles=1):
    """Load words at 0x200, apply setup, run cycles, return the cpu."""
    c = Chip8()
    out = bytearray()
    for w in words:
        out += bytes([w >> 8, w & 0xFF])
    c.load_rom(out)
    for i, val in (v or {}).items():
        c.v[i] = val
    for k in (keys or []):
        c.keys[k] = True
    for a, val in (mem or {}).items():
        c.memory[a] = val
    if delay is not None:
        c.delay = delay
    for _ in range(cycles):
        c.cycle()
    return c


def test_00e0_clears_display():
    c = Chip8()
    c.load_rom(bytes([0x00, 0xE0]))
    c.display[10] = 1
    c.cycle()
    assert sum(c.display) == 0 and c.pc == 0x202


def test_00ee_returns_from_subroutine():
    c = step(0x2204, 0x6001, 0x00EE, cycles=2)
    assert c.pc == 0x202 and c.stack == []


def test_1nnn_jumps():
    assert step(0x1300).pc == 0x300


def test_2nnn_calls_and_stacks():
    c = step(0x2300)
    assert c.pc == 0x300 and c.stack == [0x202]


def test_3xnn_skip():
    assert step(0x3205, v={2: 5}).pc == 0x204  # taken
    assert step(0x3205, v={2: 6}).pc == 0x202  # not taken


def test_4xnn_skip():
    assert step(0x4205, v={2: 9}).pc == 0x204  # taken
    assert step(0x4205, v={2: 5}).pc == 0x202  # not taken


def test_5xy0_skip():
    assert step(0x5120, v={1: 7, 2: 7}).pc == 0x204  # taken
    assert step(0x5120, v={1: 7, 2: 8}).pc == 0x202  # not taken


def test_6xnn_loads_byte():
    assert step(0x63AB).v[3] == 0xAB


def test_7xnn_adds_byte_wrapping():
    c = step(0x63FF, 0x7302, cycles=2)
    assert c.v[3] == 0x01 and c.v[0xF] == 0  # wraps, flag untouched


def test_8xy0_loads_reg():
    assert step(0x8120, v={2: 0x42}).v[1] == 0x42


def test_8xy1_or():
    assert step(0x8121, v={1: 0xF0, 2: 0x0F}).v[1] == 0xFF


def test_8xy2_and():
    assert step(0x8122, v={1: 0xF0, 2: 0x0F}).v[1] == 0x00


def test_8xy3_xor():
    assert step(0x8123, v={1: 0xFF, 2: 0x0F}).v[1] == 0xF0


def test_8xy4_add_with_carry():
    c = step(0x8124, v={1: 200, 2: 100})
    assert c.v[1] == 44 and c.v[0xF] == 1


def test_8xy4_add_without_carry():
    c = step(0x8124, v={1: 10, 2: 20})
    assert c.v[1] == 30 and c.v[0xF] == 0


def test_8xy5_sub_no_borrow():
    c = step(0x8125, v={1: 10, 2: 4})
    assert c.v[1] == 6 and c.v[0xF] == 1


def test_8xy5_sub_borrow():
    c = step(0x8125, v={1: 4, 2: 10})
    assert c.v[1] == 250 and c.v[0xF] == 0


def test_8xy6_shifts_vx_itself():
    # classic quirk: Vy ignored, Vx shifted, VF gets the old lsb
    c = step(0x8126, v={1: 0b101, 2: 0xFF})
    assert c.v[1] == 0b10 and c.v[0xF] == 1


def test_8xy7_subn():
    c = step(0x8127, v={1: 4, 2: 10})
    assert c.v[1] == 6 and c.v[0xF] == 1


def test_8xye_shifts_vx_itself():
    # classic quirk: Vy ignored, Vx shifted, VF gets the old msb
    c = step(0x812E, v={1: 0b10000001, 2: 0x00})
    assert c.v[1] == 0b10 and c.v[0xF] == 1


def test_9xy0_skip():
    assert step(0x9120, v={1: 1, 2: 2}).pc == 0x204  # taken
    assert step(0x9120, v={1: 1, 2: 1}).pc == 0x202  # not taken


def test_annn_sets_index():
    assert step(0xA321).i == 0x321


def test_bnnn_jumps_with_v0_offset():
    assert step(0xB300, v={0: 0x10}).pc == 0x310


def test_cxnn_random_masked():
    c = Chip8(seed=42)
    c.load_rom(bytes([0xC1, 0x0F]))
    c.cycle()
    expect = random.Random(42).randrange(256) & 0x0F
    assert c.v[1] == expect <= 0x0F


def test_dxyn_draws_and_collides():
    c = step(0xA300, 0x6000, 0x6100, 0xD011, mem={0x300: 0x80}, cycles=4)
    assert c.display[0] == 1 and c.v[0xF] == 0
    c.pc = 0x206  # draw the same sprite again
    c.cycle()
    assert c.display[0] == 0 and c.v[0xF] == 1  # xor erases, collision set


def test_ex9e_skips_when_key_down():
    c = step(0xE19E, v={1: 5}, keys=[5])
    assert c.pc == 0x204
    assert step(0xE19E, v={1: 5}).pc == 0x202


def test_exa1_skips_when_key_up():
    assert step(0xE1A1, v={1: 5}).pc == 0x204
    assert step(0xE1A1, v={1: 5}, keys=[5]).pc == 0x202


def test_fx07_reads_delay_timer():
    assert step(0xF107, delay=33).v[1] == 33


def test_fx0a_blocks_until_key():
    c = Chip8()
    c.load_rom(bytes([0xF1, 0x0A]))
    c.cycle()
    assert c.waiting_for_key and c.pc == 0x200
    c.cycle()
    assert c.waiting_for_key  # still waiting
    c.keys[9] = True
    c.cycle()
    assert not c.waiting_for_key and c.v[1] == 9 and c.pc == 0x202


def test_fx15_sets_delay_timer():
    assert step(0xF115, v={1: 60}).delay == 60


def test_fx18_sets_sound_timer():
    assert step(0xF118, v={1: 20}).sound == 20


def test_fx1e_adds_to_index():
    assert step(0xA300, 0xF11E, v={1: 0x10}, cycles=2).i == 0x310


def test_fx29_points_at_font():
    c = step(0xF129, v={1: 0xA})
    assert c.i == 0x050 + 0xA * 5
    assert c.memory[c.i] == 0xF0  # first byte of the A glyph


def test_fx33_stores_bcd():
    c = step(0xA300, 0xF133, v={1: 123}, cycles=2)
    assert (c.memory[0x300], c.memory[0x301], c.memory[0x302]) == (1, 2, 3)


def test_fx55_stores_registers_leaves_i():
    c = step(0xA300, 0xF255, v={0: 11, 1: 22, 2: 33}, cycles=2)
    assert (c.memory[0x300], c.memory[0x301], c.memory[0x302]) == (11, 22, 33)
    assert c.i == 0x300


def test_fx65_loads_registers_leaves_i():
    c = step(0xA300, 0xF265, mem={0x300: 11, 0x301: 22, 0x302: 33}, cycles=2)
    assert (c.v[0], c.v[1], c.v[2]) == (11, 22, 33)
    assert c.i == 0x300


def test_timers_tick_down_and_clamp():
    c = step(0x6000, delay=5)
    c.sound = 3
    c.tick()
    assert (c.delay, c.sound) == (4, 2)
    for _ in range(10):
        c.tick()
    assert (c.delay, c.sound) == (0, 0)  # never goes negative
