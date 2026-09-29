"""deterministic input recording and replay.

records the keypad mask each tick so a run can be played back
exactly. the rng seed is stored too, so rnd is deterministic.
"""
import struct


class Recorder:
    def __init__(self, cpu):
        self.cpu = cpu
        self.frames = []
        self.seed = None

    def start(self, seed=None):
        self.frames = []
        self.seed = seed

    def tick(self):
        mask = 0
        for i, pressed in enumerate(self.cpu.keys):
            if pressed:
                mask |= 1 << i
        self.frames.append(mask)

    def save(self, path):
        with open(path, "wb") as f:
            f.write(b"CH8R")
            f.write(struct.pack(">I", len(self.frames)))
            for mask in self.frames:
                f.write(struct.pack(">H", mask))

    @staticmethod
    def load(path):
        with open(path, "rb") as f:
            magic = f.read(4)
            assert magic == b"CH8R", "not a recording"
            n = struct.unpack(">I", f.read(4))[0]
            frames = []
            for _ in range(n):
                frames.append(struct.unpack(">H", f.read(2))[0])
        return frames


class Player:
    def __init__(self, cpu, frames):
        self.cpu = cpu
        self.frames = frames
        self.pos = 0

    def tick(self):
        if self.pos >= len(self.frames):
            return False
        mask = self.frames[self.pos]
        for i in range(16):
            self.cpu.keys[i] = bool(mask & (1 << i))
        self.pos += 1
        return True

    def done(self):
        return self.pos >= len(self.frames)
