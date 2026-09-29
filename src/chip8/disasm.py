"""Disassembler: turn raw opcode bytes into readable mnemonics."""


def disassemble(op):
    nnn = op & 0x0FFF
    nn = op & 0x00FF
    x = (op & 0x0F00) >> 8
    y = (op & 0x00F0) >> 4
    n = op & 0x000F

    if op == 0x00E0:
        return "CLS"
    if op == 0x00EE:
        return "RET"
    hi = op & 0xF000
    if hi == 0x1000:
        return f"JP {nnn:#05x}"
    if hi == 0x2000:
        return f"CALL {nnn:#05x}"
    if hi == 0x3000:
        return f"SE V{x:X}, {nn:#04x}"
    if hi == 0x4000:
        return f"SNE V{x:X}, {nn:#04x}"
    if op & 0xF00F == 0x5000:
        return f"SE V{x:X}, V{y:X}"
    if hi == 0x6000:
        return f"LD V{x:X}, {nn:#04x}"
    if hi == 0x7000:
        return f"ADD V{x:X}, {nn:#04x}"
    if hi == 0x8000:
        names = {
            0x0: "LD", 0x1: "OR", 0x2: "AND", 0x3: "XOR",
            0x4: "ADD", 0x5: "SUB", 0x6: "SHR", 0x7: "SUBN", 0xE: "SHL",
        }
        if n in names:
            return f"{names[n]} V{x:X}, V{y:X}"
        return f"DB {op:#06x}"
    if op & 0xF00F == 0x9000:
        return f"SNE V{x:X}, V{y:X}"
    if hi == 0xA000:
        return f"LD I, {nnn:#05x}"
    if hi == 0xB000:
        return f"JP V0, {nnn:#05x}"
    if hi == 0xC000:
        return f"RND V{x:X}, {nn:#04x}"
    if hi == 0xD000:
        return f"DRW V{x:X}, V{y:X}, {n}"
    if op & 0xF0FF == 0xE09E:
        return f"SKP V{x:X}"
    if op & 0xF0FF == 0xE0A1:
        return f"SKNP V{x:X}"
    if op & 0xF0FF == 0xF007:
        return f"LD V{x:X}, DT"
    if op & 0xF0FF == 0xF00A:
        return f"LD V{x:X}, K"
    if op & 0xF0FF == 0xF015:
        return f"LD DT, V{x:X}"
    if op & 0xF0FF == 0xF018:
        return f"LD ST, V{x:X}"
    if op & 0xF0FF == 0xF01E:
        return f"ADD I, V{x:X}"
    if op & 0xF0FF == 0xF029:
        return f"LD F, V{x:X}"
    if op & 0xF0FF == 0xF033:
        return f"LD B, V{x:X}"
    if op & 0xF0FF == 0xF055:
        return f"LD [I], V{x:X}"
    if op & 0xF0FF == 0xF065:
        return f"LD V{x:X}, [I]"
    return f"DB {op:#06x}"


def disassemble_range(memory, start, count):
    """Disassemble `count` instructions starting at address `start`."""
    lines = []
    addr = start
    for _ in range(count):
        op = (memory[addr] << 8) | memory[addr + 1]
        lines.append((addr, op, disassemble(op)))
        addr += 2
    return lines
