"""CPU core for the CHIP-8 emulator.

Memory map: 4K total. Fontset lives at 0x050-0x0A0, programs load at 0x200.
Classic shift quirk: 8XY6/8XYE shift Vx directly, ignoring Vy.
FX55/FX65 leave I unchanged (the modern behavior).
"""

import random

MEM_SIZE = 4096
DISPLAY_W = 64
DISPLAY_H = 32
STACK_DEPTH = 16
ROM_START = 0x200
FONT_START = 0x050

# the classic hex fontset, 5 bytes per glyph, 0-F
FONTSET = [
    0xF0, 0x90, 0x90, 0x90, 0xF0,  # 0
    0x20, 0x60, 0x20, 0x20, 0x70,  # 1
    0xF0, 0x10, 0xF0, 0x80, 0xF0,  # 2
    0xF0, 0x10, 0xF0, 0x10, 0xF0,  # 3
    0x90, 0x90, 0xF0, 0x10, 0x10,  # 4
    0xF0, 0x80, 0xF0, 0x10, 0xF0,  # 5
    0xF0, 0x80, 0xF0, 0x90, 0xF0,  # 6
    0xF0, 0x10, 0x20, 0x40, 0x40,  # 7
    0xF0, 0x90, 0xF0, 0x90, 0xF0,  # 8
    0xF0, 0x90, 0xF0, 0x10, 0xF0,  # 9
    0xF0, 0x90, 0xF0, 0x90, 0x90,  # A
    0xE0, 0x90, 0xE0, 0x90, 0xE0,  # B
    0xF0, 0x80, 0x80, 0x80, 0xF0,  # C
    0xE0, 0x90, 0x90, 0x90, 0xE0,  # D
    0xF0, 0x80, 0xF0, 0x80, 0xF0,  # E
    0xF0, 0x80, 0xF0, 0x80, 0x80,  # F
]


class Chip8:
    def __init__(self, seed=None):
        self.memory = bytearray(MEM_SIZE)
        self.memory[FONT_START:FONT_START + len(FONTSET)] = bytes(FONTSET)
        self.v = bytearray(16)      # V0-VF registers
        self.i = 0                  # index register
        self.pc = ROM_START         # program counter
        self.stack = []             # call stack
        self.delay = 0              # delay timer
        self.sound = 0              # sound timer
        self.keys = [False] * 16    # hex keypad state
        self.display = bytearray(DISPLAY_W * DISPLAY_H)
        self.dw = DISPLAY_W         # active display width (subclasses may change)
        self.dh = DISPLAY_H         # active display height
        self.draw_flag = False      # set when display changed
        self.waiting_for_key = False  # FX0A blocked state
        self.rng = random.Random(seed)

    def load_rom(self, data, addr=ROM_START):
        self.memory[addr:addr + len(data)] = bytes(data)

    def cycle(self):
        """Fetch, decode and execute one instruction."""
        if self.waiting_for_key:
            for k, down in enumerate(self.keys):
                if down:
                    self.v[self._key_reg] = k
                    self.waiting_for_key = False
                    self.pc += 2
                    return
            return  # still waiting, pc does not advance
        op = (self.memory[self.pc] << 8) | self.memory[self.pc + 1]
        self.execute(op)

    def tick(self):
        """Decrement timers. The runner calls this at 60Hz."""
        if self.delay > 0:
            self.delay -= 1
        if self.sound > 0:
            self.sound -= 1

    # -- helpers -----------------------------------------------------

    @staticmethod
    def _x(op):
        return (op & 0x0F00) >> 8

    @staticmethod
    def _y(op):
        return (op & 0x00F0) >> 4

    @staticmethod
    def _nnn(op):
        return op & 0x0FFF

    @staticmethod
    def _nn(op):
        return op & 0x00FF

    def _draw_sprite(self, x, y, n):
        self.v[0xF] = 0
        for row in range(n):
            bits = self.memory[self.i + row]
            for col in range(8):
                if bits & (0x80 >> col):
                    px = (x + col) % self.dw
                    py = (y + row) % self.dh
                    idx = py * self.dw + px
                    if self.display[idx]:
                        self.v[0xF] = 1
                    self.display[idx] ^= 1
        self.draw_flag = True

    def execute(self, op):
        nnn = self._nnn(op)
        nn = self._nn(op)
        x = self._x(op)
        y = self._y(op)
        n = op & 0x000F

        if op == 0x00E0:
            self.display = bytearray(len(self.display))
            self.draw_flag = True
            self.pc += 2
        elif op == 0x00EE:
            self.pc = self.stack.pop()
        elif op & 0xF000 == 0x1000:
            self.pc = nnn
        elif op & 0xF000 == 0x2000:
            if len(self.stack) >= STACK_DEPTH:
                raise RuntimeError("stack overflow")
            self.stack.append(self.pc + 2)
            self.pc = nnn
        elif op & 0xF000 == 0x3000:
            self.pc += 4 if self.v[x] == nn else 2
        elif op & 0xF000 == 0x4000:
            self.pc += 4 if self.v[x] != nn else 2
        elif op & 0xF00F == 0x5000:
            self.pc += 4 if self.v[x] == self.v[y] else 2
        elif op & 0xF000 == 0x6000:
            self.v[x] = nn
            self.pc += 2
        elif op & 0xF000 == 0x7000:
            self.v[x] = (self.v[x] + nn) & 0xFF
            self.pc += 2
        elif op & 0xF000 == 0x8000:
            self._exec_8(op, x, y)
        elif op & 0xF00F == 0x9000:
            self.pc += 4 if self.v[x] != self.v[y] else 2
        elif op & 0xF000 == 0xA000:
            self.i = nnn
            self.pc += 2
        elif op & 0xF000 == 0xB000:
            self.pc = nnn + self.v[0]
        elif op & 0xF000 == 0xC000:
            self.v[x] = self.rng.randrange(256) & nn
            self.pc += 2
        elif op & 0xF000 == 0xD000:
            self._draw_sprite(self.v[x], self.v[y], n)
            self.pc += 2
        elif op & 0xF0FF == 0xE09E:
            self.pc += 4 if self.keys[self.v[x]] else 2
        elif op & 0xF0FF == 0xE0A1:
            self.pc += 4 if not self.keys[self.v[x]] else 2
        elif op & 0xF0FF == 0xF007:
            self.v[x] = self.delay
            self.pc += 2
        elif op & 0xF0FF == 0xF00A:
            self.waiting_for_key = True
            self._key_reg = x
        elif op & 0xF0FF == 0xF015:
            self.delay = self.v[x]
            self.pc += 2
        elif op & 0xF0FF == 0xF018:
            self.sound = self.v[x]
            self.pc += 2
        elif op & 0xF0FF == 0xF01E:
            self.i = (self.i + self.v[x]) & 0xFFF
            self.pc += 2
        elif op & 0xF0FF == 0xF029:
            self.i = FONT_START + self.v[x] * 5
            self.pc += 2
        elif op & 0xF0FF == 0xF033:
            val = self.v[x]
            self.memory[self.i] = val // 100
            self.memory[self.i + 1] = (val // 10) % 10
            self.memory[self.i + 2] = val % 10
            self.pc += 2
        elif op & 0xF0FF == 0xF055:
            self.memory[self.i:self.i + x + 1] = self.v[:x + 1]
            self.pc += 2
        elif op & 0xF0FF == 0xF065:
            self.v[:x + 1] = self.memory[self.i:self.i + x + 1]
            self.pc += 2
        else:
            raise RuntimeError(f"unknown opcode {op:04X} at {self.pc:04X}")

    def _exec_8(self, op, x, y):
        kind = op & 0x000F
        if kind == 0x0:
            self.v[x] = self.v[y]
        elif kind == 0x1:
            self.v[x] |= self.v[y]
        elif kind == 0x2:
            self.v[x] &= self.v[y]
        elif kind == 0x3:
            self.v[x] ^= self.v[y]
        elif kind == 0x4:
            total = self.v[x] + self.v[y]
            self.v[0xF] = 1 if total > 0xFF else 0
            self.v[x] = total & 0xFF
        elif kind == 0x5:
            self.v[0xF] = 1 if self.v[x] >= self.v[y] else 0
            self.v[x] = (self.v[x] - self.v[y]) & 0xFF
        elif kind == 0x6:
            # classic quirk: shift Vx itself, Vy ignored
            self.v[0xF] = self.v[x] & 0x1
            self.v[x] >>= 1
        elif kind == 0x7:
            self.v[0xF] = 1 if self.v[y] >= self.v[x] else 0
            self.v[x] = (self.v[y] - self.v[x]) & 0xFF
        elif kind == 0xE:
            # classic quirk: shift Vx itself, Vy ignored
            self.v[0xF] = (self.v[x] & 0x80) >> 7
            self.v[x] = (self.v[x] << 1) & 0xFF
        else:
            raise RuntimeError(f"unknown 8-opcode {op:04X} at {self.pc:04X}")
        self.pc += 2
