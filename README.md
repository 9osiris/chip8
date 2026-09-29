# chip8

A CHIP-8 emulator written in pure Python, standard library only. It runs real
CHIP-8 ROMs in your terminal: full CPU with all 35 opcodes, Super-CHIP 1.1
hires mode, a 64x32 display, timers, hex keypad input, a disassembler, an
interactive debugger, a curses TUI, a full macro assembler, and seven
hand-written games to play.

## layout

- `src/chip8/cpu.py` - the CPU: memory, registers, all 35 opcodes, timers, keypad
- `src/chip8/schip.py` - Super-CHIP 1.1: 128x64 hires, 16x16 sprites, RPL flags
- `src/chip8/disasm.py` - disassembler, opcode bytes to mnemonics
- `src/chip8/runner.py` - terminal runner, renders the display as text
- `src/chip8/debugger.py` - interactive debugger with breakpoints
- `src/chip8/tui.py` - curses debugger TUI with pure renderers
- `src/chip8/savestate.py` - save and restore full machine state
- `src/chip8/replay.py` - deterministic input recording and playback
- `src/chip8/trace.py` - instruction trace logger
- `src/chip8/prof.py` - opcode profiler, hot blocks, heatmap
- `tools/asm/` - full assembler: lexer, expressions, macros, listings
- `tools/assemble.py` - backwards-compatible wrapper
- `tools/wav.py` - square-wave wav generator for beeps
- `roms/` - `.asm` sources and assembled `.ch8` binaries
- `tests/` - per-opcode unit tests, known-answer ROMs, rom gameplay tests

## quirks

CHIP-8 was implemented slightly differently on every machine, so a few
opcodes have famous ambiguities. This is what I picked:

- **shift (8XY6 / 8XYE)**: shifts Vx directly and ignores Vy. This is the
  original COSMAC VIP behavior, and what most old ROMs expect.
- **store/load (FX55 / FX65)**: I is left unchanged. The original hardware
  incremented it, but modern emulators and ROMs assume it stays put.
- **jump offset (BNNN)**: jumps to NNN + V0 (the classic version, not Vx).
- **draw (DXYN)**: sprites wrap around the screen edges, VF is set on any
  pixel collision.

## running a rom

```bash
cd src
python3 -m chip8.runner ../roms/bounce.ch8
```

The keyboard maps to the hex keypad like this:

```
1 2 3 4     ->  1 2 3 C
q w e r     ->  4 5 6 D
a s d f     ->  7 8 9 E
z x c v     ->  A 0 B F
```

In `catch.ch8`, `q` moves the paddle left and `r` moves it right. The terminal
bell rings when the sound timer fires. Ctrl-C quits.

## debugger

```bash
cd src
python3 -m chip8.debugger ../roms/catch.ch8
```

Commands: `step` (s), `run` (c), `break <hex addr>` (b), `regs`, `mem <addr>`,
`dis`, `key <hex> on|off` (fake keypad input, handy for testing EX9E/FX0A),
`load <file>`, `help`, `quit`.

## the roms

All ROMs were written by hand in the assembler syntax in `tools/asm/`
and assembled to raw binaries. The `.asm` files are the source of truth.

- **bounce** (`roms/bounce.asm`): a 5-byte sprite bouncing off all four edges
  of the screen. X and Y each get a direction register holding 1 or 255
  (which is -1 in unsigned math), flipped at the edges.
- **catch** (`roms/catch.asm`): a tiny game. Move the paddle with keypad 4/6,
  catch the falling pixel. Each catch bumps the score register and beeps.
  Missing it just drops a new pixel from a random column.
- **pong** (`roms/pong.asm`): player paddle on the left, auto paddle on the
  right. Keys 5/8 move. Score on paddle hits, lose on miss.
- **snake** (`roms/snake.asm`): 16x8 grid, steer with 5/8/7/9, eat to grow.
  Dies on wall or self hit. Key 5 restarts.
- **breakout** (`roms/breakout.asm`): 40 bricks, paddle on 4/6, ball breaks
  bricks for score. Win by clearing all, lose by missing.
- **life** (`roms/life.asm`): Conway's Game of Life on a 32x16 torus. Starts
  with a glider and blinker. Key 0 seeds a random soup.
- **invaders** (`roms/invaders.asm`): 8 aliens march and drop, you shoot with
  5, move with 4/6. Aliens shoot back. Win by clearing all 8.

## tests

```bash
python3 -c "
from tests import test_opcodes, test_kats
n = 0
for mod in (test_opcodes, test_kats):
    for name in dir(mod):
        if name.startswith('test_'):
            getattr(mod, name)(); n += 1
print(n, 'passed')
"
```

Every opcode has at least one unit test checking its side effects on
registers, memory, or the display. `test_kats.py` runs a hand-assembled
program to completion and asserts the exact final register and memory state.
