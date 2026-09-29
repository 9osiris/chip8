"""Known-answer test: a hand-assembled ROM with a predictable final state.

The program exercises arithmetic, shifts, index ops, memory store/load,
the font pointer, BCD, and a jump over dead code, then spins on JP self.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from chip8.cpu import Chip8

# hand-assembled: see the comments in test_known_answer_rom
KAT_ROM = bytes([
    0x60, 0x05,  # LD V0, 5
    0x61, 0x07,  # LD V1, 7
    0x62, 0x03,  # LD V2, 3
    0x80, 0x14,  # ADD V0, V1      -> V0 = 12
    0x80, 0x25,  # SUB V0, V2      -> V0 = 9, VF = 1
    0x81, 0x27,  # SUBN V1, V2     -> V1 = 3-7 = 252, VF = 0
    0x82, 0x06,  # SHR V2          -> V2 = 1, VF = 1
    0xA3, 0x00,  # LD I, 0x300
    0xF2, 0x55,  # LD [I], V2      -> mem[300..302] = 9, 252, 1
    0x60, 0x00,  # LD V0, 0
    0x61, 0x00,  # LD V1, 0
    0x62, 0x00,  # LD V2, 0
    0xF2, 0x65,  # LD V2, [I]      -> V0..V2 = 9, 252, 1
    0xF0, 0x29,  # LD F, V0        -> I = 0x50 + 9*5 = 0x7D
    0x63, 0x7B,  # LD V3, 123
    0xF3, 0x33,  # LD B, V3        -> mem[7D..7F] = 1, 2, 3
    0x12, 0x24,  # JP 0x224
    0x60, 0xFF,  # LD V0, 0xFF     (dead code, skipped)
    0x70, 0x01,  # ADD V0, 1       -> V0 = 10
    0x12, 0x26,  # JP 0x226        (halt: spin here)
])


def test_known_answer_rom():
    c = Chip8()
    c.load_rom(KAT_ROM)
    for _ in range(30):
        c.cycle()

    assert c.v[0] == 10
    assert c.v[1] == 252
    assert c.v[2] == 1
    assert c.v[3] == 123
    assert c.v[0xF] == 1  # last flag write was SHR V2 (lsb was 1)

    assert c.memory[0x300] == 9
    assert c.memory[0x301] == 252
    assert c.memory[0x302] == 1

    assert c.i == 0x7D
    assert c.memory[0x7D] == 1
    assert c.memory[0x7E] == 2
    assert c.memory[0x7F] == 3

    assert c.pc == 0x226  # spinning on the halt jump
    assert c.stack == []
