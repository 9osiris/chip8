"""Curses debugger TUI for CHIP-8 ROMs.

All rendering lives in pure functions (format_*, layout, render_frame)
so the whole UI is testable without a terminal. The curses loop at the
bottom is thin: it only draws the pre-rendered panes and maps keys to
debugger actions.

Keys:
  space/s  step one instruction        c      run until breakpoint/key
  b        toggle breakpoint at PC     w      add a watch expression
  x        drop the last watch         up/dn  scroll the memory view
  pgup/dn  scroll memory a page        q      quit
"""

import curses

from chip8.cpu import Chip8
from chip8.disasm import disassemble
from chip8.schip import SuperChip8, disassemble_schip


class WatchError(Exception):
    pass


class UiState:
    def __init__(self):
        self.breakpoints = set()
        self.watches = []     # list of expression strings
        self.mem_addr = 0x200
        self.running = False


# -- pure rendering --------------------------------------------------------

def _dis_fn(cpu):
    if isinstance(cpu, SuperChip8):
        return disassemble_schip
    return disassemble


def format_regs(cpu):
    """Register pane lines: V0-VF in rows of four, then I/PC/DT/ST/SP."""
    lines = []
    for base in range(0, 16, 4):
        lines.append(" ".join(f"V{i:X}={cpu.v[i]:02X}"
                              for i in range(base, base + 4)))
    lines.append(f"I={cpu.i:03X} PC={cpu.pc:04X} "
                 f"DT={cpu.delay:02X} ST={cpu.sound:02X}")
    lines.append(f"SP={len(cpu.stack)}")
    return lines


def format_disasm(cpu, breakpoints, before=6, after=12):
    """Disassembly centered on PC. '>' marks PC, '*' marks breakpoints."""
    dis = _dis_fn(cpu)
    start = max(0x200, cpu.pc - before * 2)
    lines = []
    addr = start
    for _ in range(before + after + 1):
        if addr > 0xFFE:
            break
        op = (cpu.memory[addr] << 8) | cpu.memory[addr + 1]
        cur = ">" if addr == cpu.pc else " "
        bp = "*" if addr in breakpoints else " "
        lines.append(f"{cur}{bp}{addr:04X}: {op:04X}  {dis(op)}")
        addr += 2
    return lines


def format_stack(cpu):
    """Call stack pane, top of stack first."""
    if not cpu.stack:
        return ["(empty)"]
    return [f"{i}: {addr:04X}" for i, addr in
            enumerate(reversed(cpu.stack))]


def format_mem(cpu, addr, rows=8, cols=8):
    """Hex dump with ascii gutter, clamped to memory bounds."""
    lines = []
    for r in range(rows):
        a = addr + r * cols
        if a >= len(cpu.memory):
            break
        chunk = cpu.memory[a:a + cols]
        hexs = " ".join(f"{b:02X}" for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{a:04X}: {hexs:<{cols * 3 - 1}} |{asc}|")
    return lines


def format_breakpoints(breakpoints):
    if not breakpoints:
        return ["(none)"]
    return [f"{a:04X}" for a in sorted(breakpoints)]


def format_watches(cpu, watches):
    lines = []
    for expr in watches:
        try:
            val = eval_watch(cpu, expr)
            lines.append(f"{expr} = {val} ({val:#x})")
        except WatchError as e:
            lines.append(f"{expr} = <err: {e}>")
    return lines or ["(none)"]


def layout(w, h):
    """Pane rectangles for a terminal of w x h: name -> (x, y, w, h)."""
    w = max(w, 70)
    h = max(h, 28)  # keeps every pane at a positive height
    right_w = 36
    mem_h = 10
    mid = h - mem_h
    panes = {}
    panes["disasm"] = (0, 0, w - right_w - 1, mid)
    panes["regs"] = (w - right_w, 0, right_w, 7)
    panes["stack"] = (w - right_w, 7, right_w, 6)
    remaining = mid - 13
    watch_h = max(2, remaining * 2 // 3)
    bp_h = max(1, remaining - watch_h)
    panes["watches"] = (w - right_w, 13, right_w, watch_h)
    panes["breakpoints"] = (w - right_w, 13 + watch_h, right_w, bp_h)
    panes["mem"] = (0, mid, w, mem_h)
    panes["status"] = (0, h - 1, w, 1)
    return panes


def render_frame(cpu, ui, width=100, height=30):
    """Render every pane and clip lines to the pane rectangles."""
    panes = layout(width, height)
    content = {
        "disasm": format_disasm(cpu, ui.breakpoints),
        "regs": format_regs(cpu),
        "stack": format_stack(cpu),
        "watches": format_watches(cpu, ui.watches),
        "breakpoints": format_breakpoints(ui.breakpoints),
        "mem": format_mem(cpu, ui.mem_addr),
        "status": [status_line(cpu, ui)],
    }
    frame = {}
    for name, lines in content.items():
        _, _, pw, ph = panes[name]
        clipped = [line[:pw] for line in lines[:ph]]
        frame[name] = clipped
    return frame, panes


def status_line(cpu, ui):
    mode = "schip" if isinstance(cpu, SuperChip8) else "chip8"
    bps = len(ui.breakpoints)
    return (f"{mode} pc={cpu.pc:04X} bps={bps} watches={len(ui.watches)} "
            f"[space] step [c] run [b] break [w] watch [q] quit")


# -- watch expressions -----------------------------------------------------
# small recursive descent evaluator: numbers, V0-VF, I, PC, DT, ST, SP,
# the usual operators with c-like precedence, parens, unary minus/~.

_WATCH_OPS = ("<<", ">>", "+", "-", "*", "/", "%", "&", "|", "^", "~",
              "(", ")")


def _watch_lex(text):
    toks = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
        elif ch.isalpha() or ch == "_":
            j = i
            while j < len(text) and (text[j].isalnum() or text[j] == "_"):
                j += 1
            toks.append(("id", text[i:j].upper()))
            i = j
        elif ch.isdigit():
            j = i
            while j < len(text) and text[j].isalnum():
                j += 1
            word = text[i:j]
            try:
                toks.append(("num", int(word, 0)))
            except ValueError:
                raise WatchError(f"bad number {word}")
            i = j
        else:
            two = text[i:i + 2]
            if two in ("<<", ">>"):
                toks.append(("op", two))
                i += 2
            elif ch in "+-*/%&|^~()":
                toks.append(("op", ch))
                i += 1
            else:
                raise WatchError(f"bad character {ch!r}")
    return toks


def _watch_symbol(cpu, name):
    if len(name) == 2 and name[0] == "V" and name[1] in "0123456789ABCDEF":
        return cpu.v[int(name[1], 16)]
    if name == "I":
        return cpu.i
    if name == "PC":
        return cpu.pc
    if name == "DT":
        return cpu.delay
    if name == "ST":
        return cpu.sound
    if name == "SP":
        return len(cpu.stack)
    raise WatchError(f"unknown name {name}")


class _WatchParser:
    def __init__(self, toks, cpu):
        self.toks = toks
        self.cpu = cpu
        self.pos = 0

    def peek(self):
        return self.toks[self.pos] if self.pos < len(self.toks) else (None, None)

    def next(self):
        tok = self.peek()
        self.pos += 1
        return tok

    def expect_op(self, op):
        kind, val = self.next()
        if kind != "op" or val != op:
            raise WatchError(f"expected {op!r}")

    def parse(self):
        val = self.parse_or()
        if self.pos != len(self.toks):
            raise WatchError("trailing tokens")
        return val

    def parse_or(self):
        val = self.parse_xor()
        while self.peek() == ("op", "|"):
            self.next()
            val |= self.parse_xor()
        return val

    def parse_xor(self):
        val = self.parse_and()
        while self.peek() == ("op", "^"):
            self.next()
            val ^= self.parse_and()
        return val

    def parse_and(self):
        val = self.parse_shift()
        while self.peek() == ("op", "&"):
            self.next()
            val &= self.parse_shift()
        return val

    def parse_shift(self):
        val = self.parse_add()
        while True:
            if self.peek() == ("op", "<<"):
                self.next()
                val <<= self.parse_add()
            elif self.peek() == ("op", ">>"):
                self.next()
                val >>= self.parse_add()
            else:
                return val

    def parse_add(self):
        val = self.parse_mul()
        while True:
            if self.peek() == ("op", "+"):
                self.next()
                val += self.parse_mul()
            elif self.peek() == ("op", "-"):
                self.next()
                val -= self.parse_mul()
            else:
                return val

    def parse_mul(self):
        val = self.parse_unary()
        while True:
            kind, op = self.peek()
            if kind == "op" and op in ("*", "/", "%"):
                self.next()
                rhs = self.parse_unary()
                if op == "*":
                    val *= rhs
                elif op == "/":
                    if rhs == 0:
                        raise WatchError("division by zero")
                    val //= rhs
                else:
                    if rhs == 0:
                        raise WatchError("division by zero")
                    val %= rhs
            else:
                return val

    def parse_unary(self):
        kind, op = self.peek()
        if kind == "op" and op == "-":
            self.next()
            return -self.parse_unary()
        if kind == "op" and op == "~":
            self.next()
            return ~self.parse_unary()
        if kind == "op" and op == "+":
            self.next()
            return self.parse_unary()
        return self.parse_primary()

    def parse_primary(self):
        kind, val = self.next()
        if kind == "num":
            return val
        if kind == "id":
            return _watch_symbol(self.cpu, val)
        if (kind, val) == ("op", "("):
            out = self.parse_or()
            self.expect_op(")")
            return out
        raise WatchError("expected a value")


def eval_watch(cpu, text):
    """Evaluate a watch expression against the cpu state."""
    if not text.strip():
        raise WatchError("empty expression")
    toks = _watch_lex(text)
    return _WatchParser(toks, cpu).parse()


# -- thin curses loop ------------------------------------------------------

class TuiApp:
    def __init__(self, cpu):
        self.cpu = cpu
        self.ui = UiState()

    def step(self):
        pc = self.cpu.pc
        self.cpu.cycle()
        self.cpu.tick()
        return pc

    def run_until_stop(self, stdscr):
        # run with a timeout so a keypress can interrupt
        stdscr.timeout(16)
        while True:
            for _ in range(12):
                if self.cpu.pc in self.ui.breakpoints:
                    self.ui.running = False
                    return
                if getattr(self.cpu, "exited", False):
                    self.ui.running = False
                    return
                try:
                    self.cpu.cycle()
                except RuntimeError:
                    self.ui.running = False
                    return
                self.cpu.tick()
            self.draw(stdscr)
            if stdscr.getch() != -1:
                self.ui.running = False
                return

    def draw(self, stdscr):
        stdscr.erase()
        frame, panes = render_frame(self.cpu, self.ui,
                                    curses.COLS, curses.LINES)
        titles = {
            "disasm": "disassembly", "regs": "registers",
            "stack": "stack", "watches": "watches",
            "breakpoints": "breakpoints", "mem": "memory",
        }
        for name, lines in frame.items():
            if name == "status":
                continue
            x, y, pw, ph = panes[name]
            title = f"-- {titles[name]} --"
            try:
                stdscr.addnstr(y, x, title, pw)
                for i, line in enumerate(lines):
                    if i + 1 < ph:
                        stdscr.addnstr(y + 1 + i, x, line, pw)
            except curses.error:
                pass
        x, y, pw, _ = panes["status"]
        try:
            stdscr.addnstr(y, x, frame["status"][0], pw,
                           curses.A_REVERSE)
        except curses.error:
            pass
        stdscr.refresh()

    def prompt(self, stdscr, text):
        curses.echo()
        try:
            stdscr.addstr(curses.LINES - 1, 0, text)
            stdscr.clrtoeol()
            out = stdscr.getstr(curses.LINES - 1, len(text)).decode()
        except curses.error:
            out = ""
        finally:
            curses.noecho()
        return out

    def handle_key(self, stdscr, ch):
        if ch in (ord("q"), 27):
            return False
        if ch in (ord(" "), ord("s")):
            self.step()
        elif ch == ord("c"):
            self.ui.running = True
            self.run_until_stop(stdscr)
            stdscr.timeout(-1)
        elif ch == ord("b"):
            pc = self.cpu.pc
            if pc in self.ui.breakpoints:
                self.ui.breakpoints.remove(pc)
            else:
                self.ui.breakpoints.add(pc)
        elif ch == ord("w"):
            expr = self.prompt(stdscr, "watch: ")
            if expr.strip():
                self.ui.watches.append(expr.strip())
        elif ch == ord("x"):
            if self.ui.watches:
                self.ui.watches.pop()
        elif ch == curses.KEY_UP:
            self.ui.mem_addr = max(0, self.ui.mem_addr - 8)
        elif ch == curses.KEY_DOWN:
            self.ui.mem_addr = min(0x1000 - 64, self.ui.mem_addr + 8)
        elif ch == curses.KEY_PPAGE:
            self.ui.mem_addr = max(0, self.ui.mem_addr - 64)
        elif ch == curses.KEY_NPAGE:
            self.ui.mem_addr = min(0x1000 - 64, self.ui.mem_addr + 64)
        return True

    def run(self, stdscr):
        curses.curs_set(0)
        stdscr.timeout(-1)
        while True:
            self.draw(stdscr)
            if not self.handle_key(stdscr, stdscr.getch()):
                break


def main(argv):
    schip = "--schip" in argv
    args = [a for a in argv if a != "--schip"]
    if len(args) != 2:
        print("usage: python3 -m chip8.tui [--schip] <rom.ch8>")
        raise SystemExit(1)
    cpu = SuperChip8() if schip else Chip8()
    cpu.load_rom(open(args[1], "rb").read())
    curses.wrapper(TuiApp(cpu).run)


if __name__ == "__main__":
    import sys
    main(sys.argv)
