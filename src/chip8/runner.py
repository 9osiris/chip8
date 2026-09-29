"""Terminal runner: play a CHIP-8 ROM in your terminal.

Renders the 64x32 display as text, maps your keyboard to the hex keypad,
ticks the timers at 60Hz.

Usage: python3 -m chip8.runner roms/bounce.ch8
"""

import select
import sys
import termios
import time
import tty

from chip8.cpu import Chip8, DISPLAY_W, DISPLAY_H

# keyboard char -> chip8 keypad index
KEYMAP = {
    "1": 0x1, "2": 0x2, "3": 0x3, "4": 0xC,
    "q": 0x4, "w": 0x5, "e": 0x6, "r": 0xD,
    "a": 0x7, "s": 0x8, "d": 0x9, "f": 0xE,
    "z": 0xA, "x": 0x0, "c": 0xB, "v": 0xF,
}

PIXEL_ON = "#"
PIXEL_OFF = " "

CYCLES_PER_FRAME = 12  # ~720 instructions/sec at 60fps


def render(cpu):
    lines = []
    for y in range(DISPLAY_H):
        row = cpu.display[y * DISPLAY_W:(y + 1) * DISPLAY_W]
        lines.append("".join(PIXEL_ON if p else PIXEL_OFF for p in row))
    return "\n".join(lines)


def read_keys(fd):
    keys = set()
    while select.select([sys.stdin], [], [], 0)[0]:
        ch = sys.stdin.read(1)
        if ch == "\x03":  # ctrl-c
            raise KeyboardInterrupt
        if ch in KEYMAP:
            keys.add(KEYMAP[ch])
    return keys


def run(rom_path):
    cpu = Chip8()
    cpu.load_rom(open(rom_path, "rb").read())

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        sys.stdout.write("\x1b[?25l")  # hide cursor
        beeping = False
        last_tick = time.time()
        while True:
            pressed = read_keys(fd)
            cpu.keys = [i in pressed for i in range(16)]

            for _ in range(CYCLES_PER_FRAME):
                cpu.cycle()

            now = time.time()
            if now - last_tick >= 1 / 60:
                cpu.tick()
                last_tick = now

            if cpu.sound > 0 and not beeping:
                sys.stdout.write("\a")  # bell when the beep starts
                beeping = True
            elif cpu.sound == 0:
                beeping = False

            sys.stdout.write("\x1b[H")  # home cursor
            sys.stdout.write(render(cpu))
            status = f"sound:{cpu.sound} delay:{cpu.delay} pc:{cpu.pc:#06x}  (ctrl-c to quit)"
            sys.stdout.write("\n" + status + " " * 10)
            sys.stdout.flush()
            time.sleep(1 / 60)
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\x1b[?25h\n")


def main():
    if len(sys.argv) != 2:
        print("usage: python3 -m chip8.runner <rom.ch8>")
        sys.exit(1)
    run(sys.argv[1])


if __name__ == "__main__":
    main()
