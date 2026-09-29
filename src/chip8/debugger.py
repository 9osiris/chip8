"""Interactive debugger for CHIP-8 ROMs.

Commands:
  load <file>      load a rom (resets the cpu)
  step, s          execute one instruction
  run, c           run until a breakpoint or ctrl-c
  break <addr>, b  toggle a breakpoint at hex address
  regs             dump registers, I, PC, timers, stack
  mem <addr> [n]   dump n bytes of memory (default 16)
  dis [addr] [n]   disassemble n instructions (default 8) around addr/PC
  key <hex> on|off press or release a keypad key (for testing input opcodes)
  help             show this list
  quit, q          exit

Usage: python3 -m chip8.debugger roms/bounce.ch8
"""

import sys

from chip8.cpu import Chip8, DISPLAY_W, DISPLAY_H
from chip8.disasm import disassemble_range


class Debugger:
    def __init__(self):
        self.cpu = Chip8()
        self.breakpoints = set()
        self.running = True

    def load(self, path):
        self.cpu = Chip8()
        self.cpu.load_rom(open(path, "rb").read())
        self.breakpoints = set()
        print(f"loaded {path}")

    def cmd_step(self, args):
        pc = self.cpu.pc
        op = (self.cpu.memory[pc] << 8) | self.cpu.memory[pc + 1]
        from chip8.disasm import disassemble
        print(f"{pc:#06x}: {disassemble(op)}")
        self.cpu.cycle()
        self.cpu.tick()

    def cmd_run(self, args):
        print("running, ctrl-c to stop")
        try:
            while True:
                if self.cpu.pc in self.breakpoints:
                    print(f"hit breakpoint at {self.cpu.pc:#06x}")
                    break
                self.cpu.cycle()
                self.cpu.tick()
        except KeyboardInterrupt:
            print(f"\nstopped at {self.cpu.pc:#06x}")
        except RuntimeError as e:
            print(f"\nstopped with error: {e}")

    def cmd_break(self, args):
        if not args:
            bps = sorted(self.breakpoints)
            print("breakpoints:", " ".join(f"{b:#06x}" for b in bps) or "none")
            return
        addr = int(args[0], 16)
        if addr in self.breakpoints:
            self.breakpoints.remove(addr)
            print(f"removed breakpoint at {addr:#06x}")
        else:
            self.breakpoints.add(addr)
            print(f"breakpoint set at {addr:#06x}")

    def cmd_regs(self, args):
        c = self.cpu
        for i in range(0, 16, 4):
            print(" ".join(f"V{j:X}={c.v[j]:#04x}" for j in range(i, i + 4)))
        print(f"I={c.i:#05x} PC={c.pc:#06x} DT={c.delay} ST={c.sound}")
        print("stack:", " ".join(f"{a:#06x}" for a in c.stack) or "empty")

    def cmd_mem(self, args):
        addr = int(args[0], 16)
        n = int(args[1]) if len(args) > 1 else 16
        mem = self.cpu.memory
        for off in range(0, n, 8):
            chunk = mem[addr + off:addr + off + 8]
            hexs = " ".join(f"{b:02x}" for b in chunk)
            print(f"{addr + off:#06x}: {hexs}")

    def cmd_dis(self, args):
        addr = int(args[0], 16) if args else self.cpu.pc
        n = int(args[1]) if len(args) > 1 else 8
        for a, op, text in disassemble_range(self.cpu.memory, addr, n):
            marker = ">" if a == self.cpu.pc else " "
            bp = "*" if a in self.breakpoints else " "
            print(f"{marker}{bp}{a:#06x}: {op:04x}  {text}")

    def cmd_key(self, args):
        if len(args) != 2 or args[1] not in ("on", "off"):
            print("usage: key <hex> on|off  (e.g. key 4 on)")
            return
        k = int(args[0], 16)
        self.cpu.keys[k] = args[1] == "on"
        print(f"key {k:X} {'pressed' if self.cpu.keys[k] else 'released'}")

    def cmd_help(self, args):
        print(__doc__)

    def repl(self):
        cmds = {
            "step": self.cmd_step, "s": self.cmd_step,
            "run": self.cmd_run, "c": self.cmd_run,
            "break": self.cmd_break, "b": self.cmd_break,
            "regs": self.cmd_regs, "mem": self.cmd_mem,
            "dis": self.cmd_dis, "help": self.cmd_help,
            "key": self.cmd_key,
        }
        while self.running:
            try:
                line = input("(chip8) ").strip().split()
            except EOFError:
                break
            if not line:
                continue
            name, args = line[0], line[1:]
            if name in ("quit", "q"):
                break
            if name == "load":
                if args:
                    self.load(args[0])
                else:
                    print("usage: load <file>")
                continue
            fn = cmds.get(name)
            if fn:
                try:
                    fn(args)
                except Exception as e:
                    print(f"error: {e}")
            else:
                print(f"unknown command: {name} (try help)")


def main():
    dbg = Debugger()
    if len(sys.argv) == 2:
        dbg.load(sys.argv[1])
    dbg.repl()


if __name__ == "__main__":
    main()
