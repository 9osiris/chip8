"""print basic info about a .ch8 rom: size, opcode histogram, entry point."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from chip8.disasm import disassemble


def info(path):
    data = open(path, "rb").read()
    print(f"file: {path}")
    print(f"size: {len(data)} bytes")
    print(f"load addr: 0x200")
    # count opcode families
    fams = {}
    for i in range(0, len(data) - 1, 2):
        op = (data[i] << 8) | data[i + 1]
        fam = f"{op >> 12:X}xxx"
        fams[fam] = fams.get(fam, 0) + 1
    print("opcode families:")
    for fam in sorted(fams):
        print(f"  {fam}: {fams[fam]}")
    # disassemble first few
    print("first 8 instructions:")
    for i in range(0, min(16, len(data) - 1), 2):
        op = (data[i] << 8) | data[i + 1]
        print(f"  {0x200 + i:04x}: {op:04x}  {disassemble(op)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: rominfo.py <rom.ch8>")
        sys.exit(1)
    info(sys.argv[1])
