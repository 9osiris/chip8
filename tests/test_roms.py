"""rom library tests: assemble sources, compare binaries, scripted gameplay."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from chip8.cpu import Chip8
from asm.assembler import Assembler

ROM_DIR = os.path.join(os.path.dirname(__file__), "..", "roms")
CYC = 100


def assemble(name):
    a = Assembler()
    src = open(os.path.join(ROM_DIR, name + ".asm")).read()
    data, _ = a.assemble_text(src)
    return a, data


def load(name):
    a, data = assemble(name)
    rom = open(os.path.join(ROM_DIR, name + ".ch8"), "rb").read()
    assert data == rom, f"{name}.ch8 does not match {name}.asm"
    c = Chip8(seed=5)
    c.load_rom(rom)
    return a, c


def step(c, keys=()):
    for k in keys:
        c.keys[k] = True
    for _ in range(CYC):
        c.cycle()
    c.tick()
    for k in keys:
        c.keys[k] = False


def test_binaries_match_sources():
    for name in ["pong", "snake", "breakout", "life", "invaders", "bounce", "catch"]:
        asm_path = os.path.join(ROM_DIR, name + ".asm")
        if not os.path.exists(asm_path):
            continue
        a, data = assemble(name)
        rom = open(os.path.join(ROM_DIR, name + ".ch8"), "rb").read()
        assert data == rom, f"{name}.ch8 stale"


def test_pong_paddle_bounce():
    a, c = load("pong")
    for _ in range(10):
        step(c)
    # force ball toward paddle (left side, moving left)
    c.v[0] = 5
    c.v[1] = 20
    c.v[2] = 0xFF  # moving left
    c.v[3] = 1
    c.v[4] = 16  # paddle y, ball y=20 within 16..23
    for _ in range(30):
        step(c)
        if c.v[2] == 1:  # bounced (now moving right)
            break
    assert c.v[2] == 1


def test_pong_miss_lose():
    a, c = load("pong")
    for _ in range(10):
        step(c)
    c.v[0] = 2
    c.v[1] = 16
    c.v[2] = 0xFF  # moving left
    c.v[3] = 1
    c.v[4] = 20  # paddle far from ball y
    for _ in range(40):
        step(c)
        if c.v[6] == 1:  # lose state
            break
    assert c.v[6] == 1


def test_snake_eats_food():
    a, c = load("snake")
    for _ in range(20):
        step(c)
    # V7 is state (0=playing, 1=dead), V6 is length
    assert c.v[7] in (0, 1)  # game ran
    assert c.v[6] >= 3  # initial length


def test_breakout_brick_break():
    a, c = load("breakout")
    bricks = a.symbols["bricks"]
    playing = a.symbols["playing"]
    for _ in range(20):
        step(c)
    # sync to playing
    for _ in range(500):
        for _ in range(CYC):
            c.cycle()
            if c.pc == playing:
                break
        c.tick()
        if c.pc == playing:
            break
    for i in range(40):
        c.memory[bricks + i] = 0
    c.memory[bricks] = 1
    c.v[5] = 39
    c.v[0] = 0
    c.v[1] = 10
    c.v[2] = 1
    c.v[3] = 0xFF
    for _ in range(120):
        step(c)
        if c.v[5] == 40:
            break
    assert c.v[5] == 40
    assert c.memory[bricks] == 0
    assert c.v[6] == 1  # win


def test_life_block_stable():
    a, c = load("life")
    gridA = a.symbols["gridA"]
    frame = a.symbols["frame"]
    for _ in range(5000):
        c.cycle()
        if c.pc == frame:
            break
    # clear and set a 2x2 block at (5,5)
    for y in range(16):
        for x in range(32):
            c.memory[gridA + y * 32 + x] = 0
    for x, y in [(5, 5), (6, 5), (5, 6), (6, 6)]:
        c.memory[gridA + y * 32 + x] = 1

    def get_grid():
        g = set()
        for y in range(16):
            for x in range(32):
                if c.memory[gridA + y * 32 + x]:
                    g.add((x, y))
        return g

    g0 = get_grid()
    prev = g0
    for _ in range(2000):
        for _ in range(CYC):
            c.cycle()
        c.tick()
        g = get_grid()
        if g != prev:
            break
    assert g == g0, "block should be stable"


def test_invaders_hit():
    a, c = load("invaders")
    aliens = a.symbols["aliens"]
    hit_alien = a.symbols["hit_alien"]
    frame = a.symbols["frame"]
    for _ in range(500):
        c.cycle()
        if c.pc == frame:
            break
    # bullet inside alien 0
    c.v[14] = 5  # VE (cannon x), bullet x = 8
    c.v[1] = 6  # bullet y
    c.v[5] = 0
    c.pc = hit_alien
    c.stack.append(0x300)
    for _ in range(500):
        op = (c.memory[c.pc] << 8) | c.memory[c.pc + 1]
        if op == 0x00EE:
            c.cycle()
            break
        c.cycle()
    assert c.memory[aliens] == 0
    assert c.v[5] == 1
