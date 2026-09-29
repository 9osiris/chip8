"""Two-pass assembler: statements in, bytes and a listing out.

Pass 1 walks the macro-expanded statements and assigns every label an
address. Pass 2 evaluates all expressions with the full symbol table
and encodes each instruction. EQU constants are evaluated in order at
their definition; forward references to labels work because labels are
all known before pass 2.
"""

from . import expr as expr_mod
from . import lexer as lexer_mod
from . import macros as macros_mod
from . import parser as parser_mod
from .errors import AsmError
from .listing import Listing

DEFAULT_ORG = 0x200
MEM_SIZE = 4096

_MNEMONICS = {
    "CLS", "RET", "JP", "CALL", "SE", "SNE", "LD", "ADD", "OR", "AND",
    "XOR", "SUB", "SUBN", "SHR", "SHL", "RND", "DRW", "SKP", "SKNP",
    "EXIT", "LOW", "HIGH", "SCR", "SCL", "SCD",
}

_ALU_SUB = {"OR": 1, "AND": 2, "XOR": 3, "SUB": 5, "SUBN": 7}


class Assembler:
    def __init__(self):
        self.symbols = {}   # labels + EQU constants (+ -D defines)
        self.macros = {}
        self.filename = "<input>"

    # -- public ------------------------------------------------------

    def assemble_text(self, src, filename="<input>"):
        """Assemble source text. Returns (bytes, Listing)."""
        self.filename = filename
        lines = lexer_mod.lex_source(src, filename)
        stmts, macros = parser_mod.parse_source(lines, filename)
        for name, macro in macros.items():
            if name in _MNEMONICS:
                raise AsmError(
                    f"macro {macro.name!r} shadows a real mnemonic",
                    line=macro.line, source_line=macro.text,
                    filename=filename)
        self.macros = macros
        expanded = macros_mod.expand_all(stmts, macros, filename)
        self._pass1(expanded)
        return self._pass2(expanded)

    def assemble_file(self, path):
        with open(path) as f:
            return self.assemble_text(f.read(), filename=path)

    # -- passes --------------------------------------------------------

    def _eval(self, node, line, text, pc):
        return expr_mod.evaluate(node, self.symbols, pc=pc, line=line,
                                 text=text, filename=self.filename)

    def _check_room(self, addr, size, line, text):
        if addr + size > MEM_SIZE:
            raise AsmError("program does not fit in 4k of memory",
                           line=line, source_line=text,
                           filename=self.filename)

    def _pass1(self, stmts):
        addr = DEFAULT_ORG
        for st in stmts:
            if isinstance(st, parser_mod.Label):
                if st.name in self.symbols:
                    raise AsmError(f"duplicate label {st.name!r}",
                                   line=st.line, source_line=st.text,
                                   filename=self.filename)
                self.symbols[st.name] = addr
            elif isinstance(st, parser_mod.Org):
                addr = self._eval(st.expr, st.line, st.text, addr)
            elif isinstance(st, parser_mod.Equ):
                if st.name in self.symbols:
                    raise AsmError(f"duplicate symbol {st.name!r}",
                                   line=st.line, source_line=st.text,
                                   filename=self.filename)
                self.symbols[st.name] = self._eval(st.expr, st.line,
                                                   st.text, addr)
            elif isinstance(st, parser_mod.Db):
                size = sum(len(val) if kind == "string" else 1
                           for kind, val in st.items)
                self._check_room(addr, size, st.line, st.text)
                addr += size
            elif isinstance(st, parser_mod.Dw):
                self._check_room(addr, 2 * len(st.exprs), st.line,
                                 st.text)
                addr += 2 * len(st.exprs)
            elif isinstance(st, parser_mod.Instr):
                if st.mnemonic not in _MNEMONICS:
                    raise AsmError(f"unknown mnemonic {st.mnemonic!r}",
                                   line=st.line, source_line=st.text,
                                   filename=self.filename)
                self._check_room(addr, 2, st.line, st.text)
                addr += 2

    def _eval_operand(self, op, stmt, pc):
        kind = op[0]
        if kind == "expr":
            return ("num", self._eval(op[1], stmt.line, stmt.text, pc))
        if kind in ("reg", "sym", "mem_i"):
            return op
        raise AsmError(f"{stmt.mnemonic} cannot take a string here",
                       line=stmt.line, source_line=stmt.text,
                       filename=self.filename)

    def _pass2(self, stmts):
        addr = DEFAULT_ORG
        out = bytearray()
        listing = Listing()
        for st in stmts:
            if isinstance(st, parser_mod.Label):
                listing.add(self.symbols[st.name], b"", st.text)
            elif isinstance(st, parser_mod.Org):
                addr = self._eval(st.expr, st.line, st.text, addr)
                listing.add(addr, b"", st.text)
            elif isinstance(st, parser_mod.Equ):
                listing.add(addr, b"", st.text)
            elif isinstance(st, parser_mod.Db):
                data = bytearray()
                for kind, val in st.items:
                    if kind == "string":
                        data += val.encode("latin-1")
                    else:
                        data.append(self._eval(val, st.line, st.text,
                                              addr) & 0xFF)
                self._check_room(addr, len(data), st.line, st.text)
                out += data
                listing.add(addr, data, st.text)
                addr += len(data)
            elif isinstance(st, parser_mod.Dw):
                data = bytearray()
                for node in st.exprs:
                    val = self._eval(node, st.line, st.text, addr) & 0xFFFF
                    data += bytes([val >> 8, val & 0xFF])
                self._check_room(addr, len(data), st.line, st.text)
                out += data
                listing.add(addr, data, st.text)
                addr += len(data)
            elif isinstance(st, parser_mod.Instr):
                ops = [self._eval_operand(o, st, addr)
                       for o in st.operands]
                word = encode(st.mnemonic, ops, st, self.filename)
                out += bytes([word >> 8, word & 0xFF])
                listing.add(addr, bytes([word >> 8, word & 0xFF]),
                            st.text)
                addr += 2
        return bytes(out), listing


# -- instruction encoding ----------------------------------------------

def _is(op, kind):
    return op[0] == kind


def _operands_error(stmt, filename, detail):
    raise AsmError(f"{stmt.mnemonic}: {detail}",
                   line=stmt.line, source_line=stmt.text,
                   filename=filename)


def encode(mnemonic, ops, stmt, filename):
    """Encode one instruction. ops are evaluated operand tuples."""
    if len(ops) == 0:
        zeros = {"CLS": 0x00E0, "RET": 0x00EE, "EXIT": 0x00FD,
                 "LOW": 0x00FE, "HIGH": 0x00FF, "SCR": 0x00FB,
                 "SCL": 0x00FC}
        if mnemonic in zeros:
            return zeros[mnemonic]
        # fall through: the per-mnemonic handlers report the arity

    def need(n):
        if len(ops) != n:
            _operands_error(stmt, filename,
                            f"takes {n} operands, got {len(ops)}")

    if mnemonic == "JP":
        need(1)
        if not _is(ops[0], "num"):
            _operands_error(stmt, filename, "JP takes an address")
        return 0x1000 | (ops[0][1] & 0xFFF)
    if mnemonic == "CALL":
        need(1)
        if not _is(ops[0], "num"):
            _operands_error(stmt, filename, "CALL takes an address")
        return 0x2000 | (ops[0][1] & 0xFFF)
    if mnemonic in ("SE", "SNE"):
        need(2)
        if not _is(ops[0], "reg"):
            _operands_error(stmt, filename, "first operand must be Vx")
        base = 0x3000 if mnemonic == "SE" else 0x4000
        if _is(ops[1], "reg"):
            base = 0x5000 if mnemonic == "SE" else 0x9000
            return base | (ops[0][1] << 8) | (ops[1][1] << 4)
        if _is(ops[1], "num"):
            return base | (ops[0][1] << 8) | (ops[1][1] & 0xFF)
        _operands_error(stmt, filename,
                        "second operand must be Vx or a byte")
    if mnemonic == "LD":
        return _encode_ld(ops, stmt, filename)
    if mnemonic == "ADD":
        need(2)
        if _is(ops[0], "sym") and ops[0][1] == "I":
            if not _is(ops[1], "reg"):
                _operands_error(stmt, filename, "ADD I takes Vx")
            return 0xF01E | (ops[1][1] << 8)
        if not _is(ops[0], "reg"):
            _operands_error(stmt, filename, "first operand must be Vx")
        if _is(ops[1], "reg"):
            return 0x8004 | (ops[0][1] << 8) | (ops[1][1] << 4)
        if _is(ops[1], "num"):
            return 0x7000 | (ops[0][1] << 8) | (ops[1][1] & 0xFF)
        _operands_error(stmt, filename,
                        "second operand must be Vx or a byte")
    if mnemonic in _ALU_SUB:
        need(2)
        if not (_is(ops[0], "reg") and _is(ops[1], "reg")):
            _operands_error(stmt, filename, "takes two registers")
        return 0x8000 | (ops[0][1] << 8) | (ops[1][1] << 4) | \
            _ALU_SUB[mnemonic]
    if mnemonic in ("SHR", "SHL"):
        need(1)
        if not _is(ops[0], "reg"):
            _operands_error(stmt, filename, "takes one register")
        return (0x8006 if mnemonic == "SHR" else 0x800E) | \
            (ops[0][1] << 8)
    if mnemonic == "RND":
        need(2)
        if not (_is(ops[0], "reg") and _is(ops[1], "num")):
            _operands_error(stmt, filename, "takes Vx and a byte")
        return 0xC000 | (ops[0][1] << 8) | (ops[1][1] & 0xFF)
    if mnemonic == "DRW":
        need(3)
        if not (_is(ops[0], "reg") and _is(ops[1], "reg")
                and _is(ops[2], "num")):
            _operands_error(stmt, filename, "takes Vx, Vy, and a size")
        n = ops[2][1]
        if n == 16:
            return 0xD000 | (ops[0][1] << 8) | (ops[1][1] << 4)
        return 0xD000 | (ops[0][1] << 8) | (ops[1][1] << 4) | (n & 0xF)
    if mnemonic in ("SKP", "SKNP"):
        need(1)
        if not _is(ops[0], "reg"):
            _operands_error(stmt, filename, "takes one register")
        return (0xE09E if mnemonic == "SKP" else 0xE0A1) | \
            (ops[0][1] << 8)
    if mnemonic == "SCD":
        need(1)
        if not _is(ops[0], "num"):
            _operands_error(stmt, filename, "SCD takes a nibble")
        return 0x00C0 | (ops[0][1] & 0xF)
    _operands_error(stmt, filename, "unknown mnemonic")


def _encode_ld(ops, stmt, filename):
    def need(n):
        if len(ops) != n:
            _operands_error(stmt, filename,
                            f"takes {n} operands, got {len(ops)}")

    need(2)
    dst, src = ops
    # LD I, addr
    if _is(dst, "sym") and dst[1] == "I":
        if not _is(src, "num"):
            _operands_error(stmt, filename, "LD I takes an address")
        return 0xA000 | (src[1] & 0xFFF)
    # LD DT/ST/F/B/HF/RPL/[I], Vx
    if _is(dst, "sym"):
        if not _is(src, "reg"):
            _operands_error(stmt, filename,
                            f"LD {dst[1]} takes a register")
        bases = {"DT": 0xF015, "ST": 0xF018, "F": 0xF029, "B": 0xF033,
                 "HF": 0xF030, "RPL": 0xF075}
        if dst[1] not in bases:
            _operands_error(stmt, filename,
                            f"cannot load into {dst[1]}")
        return bases[dst[1]] | (src[1] << 8)
    if _is(dst, "mem_i"):
        if not _is(src, "reg"):
            _operands_error(stmt, filename, "LD [I] takes a register")
        return 0xF055 | (src[1] << 8)
    # LD Vx, ...
    if not _is(dst, "reg"):
        _operands_error(stmt, filename, "first operand must be Vx")
    x = dst[1]
    if _is(src, "reg"):
        return 0x8000 | (x << 8) | (src[1] << 4)
    if _is(src, "num"):
        return 0x6000 | (x << 8) | (src[1] & 0xFF)
    if _is(src, "sym"):
        bases = {"DT": 0xF007, "K": 0xF00A, "RPL": 0xF085}
        if src[1] not in bases:
            _operands_error(stmt, filename,
                            f"cannot load from {src[1]}")
        return bases[src[1]] | (x << 8)
    if _is(src, "mem_i"):
        return 0xF065 | (x << 8)
    _operands_error(stmt, filename, "bad second operand")
