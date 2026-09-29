"""opcode profiler and hot block detector."""
from collections import Counter


class Profiler:
    def __init__(self, cpu):
        self.cpu = cpu
        self.op_counts = Counter()
        self.addr_counts = Counter()
        self.total = 0

    def step(self):
        pc = self.cpu.pc
        op = (self.cpu.memory[pc] << 8) | self.cpu.memory[pc + 1]
        # bucket by high nibble + low nibble pattern
        key = f"{op:04x}"
        self.op_counts[key] += 1
        self.addr_counts[pc] += 1
        self.total += 1
        self.cpu.cycle()

    def run(self, cycles):
        for _ in range(cycles):
            self.step()

    def top_ops(self, n=10):
        return self.op_counts.most_common(n)

    def top_addrs(self, n=10):
        return self.addr_counts.most_common(n)

    def hot_blocks(self, threshold=0.01, n=10):
        """basic blocks that eat more than threshold of cycles."""
        # a block starts after a jump/branch target or follows a branch
        blocks = Counter()
        addrs = sorted(self.addr_counts)
        if not addrs:
            return []
        block_start = addrs[0]
        for pc in addrs:
            op = (self.cpu.memory[pc] << 8) | self.cpu.memory[pc + 1]
            hi = op & 0xF000
            # branches end a block
            if hi in (0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0x9000, 0xA000):
                blocks[block_start] += self.addr_counts[pc]
                block_start = pc + 2
            elif op == 0x00EE:
                blocks[block_start] += self.addr_counts[pc]
                block_start = pc + 2
            else:
                blocks[block_start] += self.addr_counts[pc]
        cutoff = self.total * threshold
        hot = [(a, c) for a, c in blocks.items() if c >= cutoff]
        hot.sort(key=lambda x: -x[1])
        return hot[:n]

    def heatmap(self, width=64):
        """text heatmap of execution frequency per address."""
        if not self.addr_counts:
            return ""
        max_c = max(self.addr_counts.values())
        lo = min(self.addr_counts)
        hi = max(self.addr_counts)
        lines = []
        for addr in range(lo, hi + 1, 2):
            c = self.addr_counts.get(addr, 0)
            bar = "#" * int(width * c / max_c) if max_c else ""
            lines.append(f"{addr:04x} {c:8d} {bar}")
        return "\n".join(lines)

    def report(self):
        out = [f"total cycles: {self.total}", "top opcodes:"]
        for op, cnt in self.top_ops(10):
            pct = 100.0 * cnt / self.total if self.total else 0
            out.append(f"  {op} {cnt:8d} {pct:5.1f}%")
        out.append("hot blocks:")
        for addr, cnt in self.hot_blocks():
            pct = 100.0 * cnt / self.total if self.total else 0
            out.append(f"  {addr:04x} {cnt:8d} {pct:5.1f}%")
        return "\n".join(out)
