"""known-answer test 2: sprite drawing and collision.

draws a sprite twice at the same spot. the second draw should
collide (VF=1) and erase. then draws at a new spot with no collision.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from chip8.cpu import Chip8


def test_sprite_collision_kat():
    c = Chip8(seed=1)
    # program:
    # 0x200: LD I, 0x210
    # 0x202: LD V0, 10
    # 0x204: LD V1, 5
    # 0x206: DRW V0, V1, 3
    # 0x208: DRW V0, V1, 3  (should collide)
    # 0x20A: LD V0, 20
    # 0x20C: DRW V0, V1, 3  (no collision)
    # 0x20E: JP 0x20E
    # 0x210: sprite data (3 bytes)
    prog = bytes([
        0xA2, 0x10,  # LD I, 0x210
        0x60, 0x0A,  # LD V0, 10
        0x61, 0x05,  # LD V1, 5
        0xD0, 0x13,  # DRW V0, V1, 3
        0xD0, 0x13,  # DRW V0, V1, 3
        0x60, 0x14,  # LD V0, 20
        0xD0, 0x13,  # DRW V0, V1, 3
        0x12, 0x0E,  # JP 0x20E
        0xF0, 0x90, 0x90,  # sprite at 0x210
    ])
    c.load_rom(prog)
    # first draw
    for _ in range(4):
        c.cycle()
    assert c.v[0xF] == 0, "first draw should not collide"
    # second draw (same spot)
    c.cycle()
    assert c.v[0xF] == 1, "second draw should collide"
    # draw at new spot
    c.cycle()  # LD V0, 20
    c.cycle()  # DRW
    assert c.v[0xF] == 0, "third draw should not collide"
    assert any(c.display), "display should have pixels"


def test_timer_kat():
    """delay timer decrements on tick."""
    c = Chip8(seed=1)
    prog = bytes([
        0x60, 0x0A,  # LD V0, 10
        0xF0, 0x15,  # LD DT, V0
        0x12, 0x04,  # JP 0x204
    ])
    c.load_rom(prog)
    c.cycle()  # LD V0, 10
    c.cycle()  # LD DT, V0
    assert c.delay == 10
    c.tick()
    assert c.delay == 9
    for _ in range(9):
        c.tick()
    assert c.delay == 0


def test_bcd_kat():
    """FX33 stores BCD of Vx."""
    c = Chip8(seed=1)
    prog = bytes([
        0x60, 0x7B,  # LD V0, 123
        0xA3, 0x00,  # LD I, 0x300
        0xF0, 0x33,  # LD B, V0
        0x12, 0x06,  # JP 0x206
    ])
    c.load_rom(prog)
    for _ in range(3):
        c.cycle()
    assert c.memory[0x300] == 1
    assert c.memory[0x301] == 2
    assert c.memory[0x302] == 3


def test_key_kat():
    """EX9E skips if key pressed."""
    c = Chip8(seed=1)
    prog = bytes([
        0x60, 0x05,  # LD V0, 5
        0xE0, 0x9E,  # SE K, V0 (skip if key 5 pressed)
        0x61, 0x01,  # LD V1, 1 (skipped if pressed)
        0x61, 0x02,  # LD V1, 2
        0x12, 0x08,  # JP 0x208
    ])
    c.load_rom(prog)
    c.keys[5] = True
    for _ in range(4):
        c.cycle()
    assert c.v[1] == 2, "should skip LD V1,1 when key pressed"
    # not pressed
    c2 = Chip8(seed=1)
    c2.load_rom(prog)
    for _ in range(3):
        c2.cycle()
    assert c2.v[1] == 1, "should not skip when key not pressed"
