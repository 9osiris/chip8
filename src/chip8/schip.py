"""Super-CHIP 1.1 support on top of the base CPU.

Adds the 128x64 hires mode, display scrolling, 16x16 sprites (DXY0),
the 8x10 large font (FX30), the 8 RPL user flags (FX75/FX85), and the
00CN/00FB/00FC/00FD/00FE/00FF control opcodes.

Design notes, matching how most real superchip emulators behave:
- the framebuffer is always 128x64. In lores mode only the top-left
  64x32 quadrant is used, and drawing wraps inside it.
- DXY0 in lores mode draws the 16x16 sprite at half size (8x8): each
  2x2 block of the sprite toggles one display pixel.
- scroll ops move only the active region (64x32 in lores, 128x64 in
  hires). Pixels scrolled in from the edge are cleared.
- EXIT (00FD) sets the exited flag; cycle() becomes a no-op after it.
  The runner checks this flag to stop.
- FX75/FX85 move at most 8 registers, the RPL flag count.
"""

from chip8.cpu import Chip8, FONT_START
from chip8.disasm import disassemble

HIRES_W = 128
HIRES_H = 64
LORES_W = 64
LORES_H = 32
LARGE_FONT_START = 0x100  # 16 glyphs, 10 bytes each, ends at 0x1A0

# the superchip large fontset: 8 wide, 10 tall per glyph, 0-F
LARGE_FONTSET = [
    # 0
    0x3C, 0x66, 0x66, 0x66, 0x66, 0x66, 0x66, 0x66, 0x66, 0x3C,
    # 1
    0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18,
    # 2
    0x3C, 0x66, 0x06, 0x06, 0x0C, 0x18, 0x30, 0x60, 0x66, 0x7E,
    # 3
    0x3C, 0x66, 0x06, 0x06, 0x1C, 0x06, 0x06, 0x06, 0x66, 0x3C,
    # 4
    0x0C, 0x1C, 0x3C, 0x6C, 0x66, 0x7E, 0x0C, 0x0C, 0x0C, 0x0C,
    # 5
    0x7E, 0x60, 0x60, 0x7C, 0x06, 0x06, 0x06, 0x06, 0x66, 0x3C,
    # 6
    0x3C, 0x66, 0x60, 0x60, 0x7C, 0x66, 0x66, 0x66, 0x66, 0x3C,
    # 7
    0x7E, 0x66, 0x06, 0x06, 0x0C, 0x0C, 0x18, 0x18, 0x18, 0x18,
    # 8
    0x3C, 0x66, 0x66, 0x66, 0x3C, 0x66, 0x66, 0x66, 0x66, 0x3C,
    # 9
    0x3C, 0x66, 0x66, 0x66, 0x66, 0x3E, 0x06, 0x06, 0x66, 0x3C,
    # A
    0x3C, 0x66, 0x66, 0x66, 0x7E, 0x66, 0x66, 0x66, 0x66, 0x66,
    # B
    0x7C, 0x66, 0x66, 0x66, 0x7C, 0x66, 0x66, 0x66, 0x66, 0x7C,
    # C
    0x3C, 0x66, 0x66, 0x60, 0x60, 0x60, 0x60, 0x66, 0x66, 0x3C,
    # D
    0x78, 0x6C, 0x66, 0x66, 0x66, 0x66, 0x66, 0x66, 0x6C, 0x78,
    # E
    0x7E, 0x60, 0x60, 0x60, 0x7C, 0x60, 0x60, 0x60, 0x60, 0x7E,
    # F
    0x7E, 0x60, 0x60, 0x60, 0x7C, 0x60, 0x60, 0x60, 0x60, 0x60,
]


class SuperChip8(Chip8):
    def __init__(self, seed=None):
        super().__init__(seed)
        end = LARGE_FONT_START + len(LARGE_FONTSET)
        self.memory[LARGE_FONT_START:end] = bytes(LARGE_FONTSET)
        self.display = bytearray(HIRES_W * HIRES_H)
        self._hires = False
        self.dw = LORES_W
        self.dh = LORES_H
        self.rpl = [0] * 8   # RPL user flags for FX75/FX85
        self.exited = False  # set by EXIT (00FD)

    @property
    def hires(self):
        return self._hires

    @hires.setter
    def hires(self, value):
        self._hires = bool(value)
        if self._hires:
            self.dw, self.dh = HIRES_W, HIRES_H
        else:
            self.dw, self.dh = LORES_W, LORES_H

    def pixel(self, x, y):
        """Read one pixel from the full 128x64 buffer."""
        return self.display[y * HIRES_W + x]

    def cycle(self):
        if self.exited:
            return
        super().cycle()

    def execute(self, op):
        x = (op & 0x0F00) >> 8
        if op & 0xFFF0 == 0x00C0:
            self._scroll(0, op & 0x000F)
            self.pc += 2
        elif op == 0x00FB:
            self._scroll(4, 0)
            self.pc += 2
        elif op == 0x00FC:
            self._scroll(-4, 0)
            self.pc += 2
        elif op == 0x00FD:
            self.exited = True
            self.pc += 2
        elif op == 0x00FE:
            self.hires = False
            self.pc += 2
        elif op == 0x00FF:
            self.hires = True
            self.pc += 2
        elif op & 0xF0FF == 0xF030:
            self.i = LARGE_FONT_START + self.v[x] * 10
            self.pc += 2
        elif op & 0xF0FF == 0xF075:
            n = min(x + 1, 8)
            self.rpl[:n] = self.v[:n]
            self.pc += 2
        elif op & 0xF0FF == 0xF085:
            n = min(x + 1, 8)
            self.v[:n] = self.rpl[:n]
            self.pc += 2
        else:
            super().execute(op)

    # -- drawing ----------------------------------------------------

    def _draw_sprite(self, x, y, n):
        # stride is always HIRES_W; lores uses the top-left quadrant
        if n == 0:
            self._draw_large_sprite(x, y)
            return
        self.v[0xF] = 0
        w, h = self.dw, self.dh
        for row in range(n):
            bits = self.memory[self.i + row]
            for col in range(8):
                if bits & (0x80 >> col):
                    px = (x + col) % w
                    py = (y + row) % h
                    idx = py * HIRES_W + px
                    if self.display[idx]:
                        self.v[0xF] = 1
                    self.display[idx] ^= 1
        self.draw_flag = True

    def _draw_large_sprite(self, x, y):
        # DXY0: 16x16 sprite, 32 bytes at I, drawn with xor
        self.v[0xF] = 0
        w, h = self.dw, self.dh
        if self.hires:
            for row in range(16):
                bits = (self.memory[self.i + row * 2] << 8)
                bits |= self.memory[self.i + row * 2 + 1]
                for col in range(16):
                    if bits & (0x8000 >> col):
                        px = (x + col) % w
                        py = (y + row) % h
                        idx = py * HIRES_W + px
                        if self.display[idx]:
                            self.v[0xF] = 1
                        self.display[idx] ^= 1
        else:
            # lores: half size, each 2x2 block toggles one pixel
            targets = set()
            for row in range(16):
                bits = (self.memory[self.i + row * 2] << 8)
                bits |= self.memory[self.i + row * 2 + 1]
                for col in range(16):
                    if bits & (0x8000 >> col):
                        px = (x + col // 2) % w
                        py = (y + row // 2) % h
                        targets.add((px, py))
            for px, py in targets:
                idx = py * HIRES_W + px
                if self.display[idx]:
                    self.v[0xF] = 1
                self.display[idx] ^= 1
        self.draw_flag = True

    def _scroll(self, dx, dy):
        # shift the active region; pixels shifted out are lost,
        # pixels shifted in are cleared
        w, h = self.dw, self.dh
        old = bytes(self.display)
        for y in range(h):
            for x in range(w):
                sx, sy = x - dx, y - dy
                if 0 <= sx < w and 0 <= sy < h:
                    self.display[y * HIRES_W + x] = old[sy * HIRES_W + sx]
                else:
                    self.display[y * HIRES_W + x] = 0
        self.draw_flag = True


def is_schip_op(op):
    """True if the opcode is superchip-specific (not in base chip-8)."""
    if op & 0xFFF0 == 0x00C0:
        return True
    if op in (0x00FB, 0x00FC, 0x00FD, 0x00FE, 0x00FF):
        return True
    if op & 0xF000 == 0xD000 and (op & 0x000F) == 0:
        return True
    low = op & 0xF0FF
    return low in (0xF030, 0xF075, 0xF085)


def disassemble_schip(op):
    """Disassemble one opcode, with superchip mnemonics."""
    x = (op & 0x0F00) >> 8
    y = (op & 0x00F0) >> 4
    if op & 0xFFF0 == 0x00C0:
        return f"SCD {op & 0x000F}"
    if op == 0x00FB:
        return "SCR"
    if op == 0x00FC:
        return "SCL"
    if op == 0x00FD:
        return "EXIT"
    if op == 0x00FE:
        return "LOW"
    if op == 0x00FF:
        return "HIGH"
    if op & 0xF000 == 0xD000 and (op & 0x000F) == 0:
        return f"DRW V{x:X}, V{y:X}, 16"
    if op & 0xF0FF == 0xF030:
        return f"LD HF, V{x:X}"
    if op & 0xF0FF == 0xF075:
        return f"LD RPL, V{x:X}"
    if op & 0xF0FF == 0xF085:
        return f"LD V{x:X}, RPL"
    return disassemble(op)


def disassemble_schip_range(memory, start, count):
    """Disassemble count instructions with superchip mnemonics."""
    lines = []
    addr = start
    for _ in range(count):
        op = (memory[addr] << 8) | memory[addr + 1]
        lines.append((addr, op, disassemble_schip(op)))
        addr += 2
    return lines
