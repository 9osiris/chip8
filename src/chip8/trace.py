"""instruction trace logger."""
from .disasm import disassemble


class Tracer:
    def __init__(self, cpu, out=None, max_lines=None):
        self.cpu = cpu
        self.out = out
        self.max_lines = max_lines
        self.lines = []
        self.count = 0

    def step(self):
        pc = self.cpu.pc
        op = (self.cpu.memory[pc] << 8) | self.cpu.memory[pc + 1]
        text = disassemble(op)
        regs = " ".join(f"V{i:X}={self.cpu.v[i]:02x}" for i in range(16))
        line = f"{pc:04x} {op:04x} {text:<24} {regs} I={self.cpu.i:04x}"
        if self.out:
            self.out.write(line + "\n")
        else:
            self.lines.append(line)
        self.count += 1
        if self.max_lines and self.count >= self.max_lines:
            return False
        return True

    def run(self, cycles):
        for _ in range(cycles):
            if not self.step():
                break
            self.cpu.cycle()
        return self.lines

    def save(self, path):
        with open(path, "w") as f:
            for line in self.lines:
                f.write(line + "\n")
