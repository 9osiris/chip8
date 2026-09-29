"""Parser: lexed lines become statements.

Statements: Label, Instr, Org, Db, Dw, Equ, MacroDef.
Operands are one of ("reg", n), ("expr", node), ("sym", name),
("mem_i",) for [I], or ("string", s) for DB strings.
"""

import re

from . import expr as expr_mod
from .errors import AsmError

REG = re.compile(r"^[Vv]([0-9A-Fa-f])$")
SYMS = {"I", "DT", "ST", "K", "F", "B", "HF", "RPL"}
DIRECTIVES = {"ORG", "DB", "DW"}
RESERVED = DIRECTIVES | {"EQU", "MACRO", "ENDM"}


class Label:
    def __init__(self, name, line, text):
        self.name = name
        self.line = line
        self.text = text


class Instr:
    def __init__(self, mnemonic, operands, line, text):
        self.mnemonic = mnemonic      # uppercased
        self.operands = operands
        self.line = line
        self.text = text


class Org:
    def __init__(self, expr, line, text):
        self.expr = expr
        self.line = line
        self.text = text


class Db:
    def __init__(self, items, line, text):
        self.items = items            # ("expr", node) or ("string", s)
        self.line = line
        self.text = text


class Dw:
    def __init__(self, exprs, line, text):
        self.exprs = exprs
        self.line = line
        self.text = text


class Equ:
    def __init__(self, name, expr, line, text):
        self.name = name
        self.expr = expr
        self.line = line
        self.text = text


class MacroDef:
    def __init__(self, name, params, body, line, text):
        self.name = name              # uppercased
        self.params = params          # list of names
        self.body = body              # list of statements
        self.line = line
        self.text = text


def _fail(message, ll, filename=None, tok=None):
    if tok is not None:
        raise AsmError(message, line=tok.line, col=tok.col,
                       source_line=ll.text, filename=filename)
    raise AsmError(message, line=ll.lineno, source_line=ll.text,
                   filename=filename)


def _check_name(name, ll, filename, what="label"):
    if REG.match(name):
        _fail(f"{what} {name!r} looks like a register", ll, filename)
    if name.upper() in RESERVED:
        _fail(f"{what} {name!r} is a reserved word", ll, filename)


def _split_operands(toks, ll, filename):
    """Split operand tokens on top-level commas."""
    groups, cur, depth = [], [], 0
    for tok in toks:
        if tok.kind in ("lparen", "lbracket"):
            depth += 1
            cur.append(tok)
        elif tok.kind in ("rparen", "rbracket"):
            depth -= 1
            cur.append(tok)
        elif tok.kind == "comma" and depth == 0:
            groups.append(cur)
            cur = []
        else:
            cur.append(tok)
    groups.append(cur)
    if any(not g for g in groups):
        _fail("empty operand", ll, filename)
    return groups


def parse_operand(toks, ll, filename=None):
    """Parse one operand's tokens into an operand tuple."""
    if len(toks) == 1 and toks[0].kind == "ident":
        name = toks[0].value
        m = REG.match(name)
        if m:
            return ("reg", int(m.group(1), 16))
        upper = name.upper()
        if upper in SYMS:
            return ("sym", upper)
    if (len(toks) == 3 and toks[0].kind == "lbracket"
            and toks[1].kind == "ident" and toks[1].value.upper() == "I"
            and toks[2].kind == "rbracket"):
        return ("mem_i",)
    if len(toks) == 1 and toks[0].kind == "string":
        return ("string", toks[0].value)
    node = expr_mod.parse_expr(toks, ll.lineno, ll.text, filename)
    return ("expr", node)


def _parse_body_line(ll, filename):
    """Parse one line inside a macro body (no nested macro defs)."""
    toks = list(ll.tokens)
    stmts = []
    while (toks and toks[0].kind == "ident" and len(toks) > 1
            and toks[1].kind == "colon"):
        _check_name(toks[0].value, ll, filename)
        stmts.append(Label(toks[0].value, ll.lineno, ll.text))
        toks = toks[2:]
    if not toks:
        return stmts
    head = toks[0]
    if head.kind != "ident":
        _fail("expected a mnemonic", ll, filename, head)
    word = head.value.upper()
    if word == "MACRO":
        _fail("nested macro definitions are not allowed", ll, filename)
    if len(toks) >= 2 and toks[1].kind == "ident" \
            and toks[1].value.upper() == "EQU":
        _check_name(head.value, ll, filename, "constant")
        node = expr_mod.parse_expr(toks[2:], ll.lineno, ll.text, filename)
        stmts.append(Equ(head.value, node, ll.lineno, ll.text))
        return stmts
    if word in DIRECTIVES:
        stmts.append(_parse_directive(word, toks[1:], ll, filename))
        return stmts
    operands = [parse_operand(g, ll, filename)
                for g in _split_operands(toks[1:], ll, filename)] \
        if len(toks) > 1 else []
    stmts.append(Instr(word, operands, ll.lineno, ll.text))
    return stmts


def _parse_directive(word, toks, ll, filename):
    if word == "ORG":
        if not toks:
            _fail("ORG takes exactly one operand", ll, filename)
        node = expr_mod.parse_expr(toks, ll.lineno, ll.text, filename)
        return Org(node, ll.lineno, ll.text)
    groups = _split_operands(toks, ll, filename) if toks else []
    if not groups:
        _fail(f"{word} needs at least one operand", ll, filename)
    if word == "DB":
        items = []
        for g in groups:
            op = parse_operand(g, ll, filename)
            if op[0] not in ("expr", "string"):
                _fail("DB takes numbers or strings", ll, filename)
            items.append(op)
        return Db(items, ll.lineno, ll.text)
    exprs = []
    for g in groups:
        op = parse_operand(g, ll, filename)
        if op[0] != "expr":
            _fail("DW takes numbers", ll, filename)
        exprs.append(op[1])
    return Dw(exprs, ll.lineno, ll.text)


def _parse_params(toks, ll, filename):
    params = []
    for g in _split_operands(toks, ll, filename) if toks else []:
        if len(g) != 1 or g[0].kind != "ident":
            _fail("macro parameters must be plain names", ll, filename)
        name = g[0].value
        if REG.match(name) or not name[0].isalpha():
            _fail(f"bad macro parameter {name!r}", ll, filename)
        if name in params:
            _fail(f"duplicate macro parameter {name!r}", ll, filename)
        params.append(name)
    return params


def parse_source(lines, filename=None):
    """Parse lexed lines. Returns (statements, macros dict)."""
    stmts = []
    macros = {}
    i = 0
    while i < len(lines):
        ll = lines[i]
        toks = list(ll.tokens)
        while (toks and toks[0].kind == "ident" and len(toks) > 1
                and toks[1].kind == "colon"):
            _check_name(toks[0].value, ll, filename)
            stmts.append(Label(toks[0].value, ll.lineno, ll.text))
            toks = toks[2:]
        if not toks:
            i += 1
            continue
        head = toks[0]
        if head.kind != "ident":
            _fail("expected a mnemonic", ll, filename, head)
        word = head.value.upper()
        if len(toks) >= 2 and toks[1].kind == "ident" \
                and toks[1].value.upper() == "EQU":
            _check_name(head.value, ll, filename, "constant")
            node = expr_mod.parse_expr(toks[2:], ll.lineno, ll.text,
                                       filename)
            stmts.append(Equ(head.value, node, ll.lineno, ll.text))
            i += 1
            continue
        if len(toks) >= 2 and toks[1].kind == "ident" \
                and toks[1].value.upper() == "MACRO":
            _check_name(head.value, ll, filename, "macro")
            name = head.value.upper()
            if name in macros:
                _fail(f"macro {head.value!r} defined twice", ll, filename)
            params = _parse_params(toks[2:], ll, filename)
            body, i = _collect_macro_body(lines, i + 1, filename)
            macros[name] = MacroDef(name, params, body, ll.lineno,
                                    ll.text)
            continue
        if word == "ENDM":
            _fail("ENDM without a matching MACRO", ll, filename)
        if word in DIRECTIVES:
            stmts.append(_parse_directive(word, toks[1:], ll, filename))
        else:
            operands = [parse_operand(g, ll, filename)
                        for g in _split_operands(toks[1:], ll, filename)] \
                if len(toks) > 1 else []
            stmts.append(Instr(word, operands, ll.lineno, ll.text))
        i += 1
    return stmts, macros


def _collect_macro_body(lines, i, filename):
    body = []
    while i < len(lines):
        ll = lines[i]
        toks = ll.tokens
        if toks and toks[0].kind == "ident" \
                and toks[0].value.upper() == "ENDM":
            if len(toks) > 1:
                _fail("ENDM takes no operands", ll, filename)
            return body, i + 1
        body.extend(_parse_body_line(ll, filename))
        i += 1
    last = lines[-1] if lines else None
    raise AsmError("MACRO without a matching ENDM",
                   line=last.lineno if last else None,
                   filename=filename)
