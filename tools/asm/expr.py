"""Expressions with c-like operators and precedence.

Grammar (lowest to highest precedence):
  or        := xor ('|' xor)*
  xor       := and ('^' and)*
  and       := shift ('&' shift)*
  shift     := add (('<<' | '>>') add)*
  add       := mul (('+' | '-') mul)*
  mul       := unary (('*' | '/' | '%') unary)*
  unary     := ('-' | '~' | '+') unary | primary
  primary   := number | name | '$' | '(' or ')'

Names resolve against the symbol table (labels, EQU constants).
'$' is the address of the instruction being assembled, so 'JP $'
spins forever. Division is truncating; division by zero is an error.
"""

from .errors import AsmError


# nodes are tuples: ("num", v), ("id", name), ("neg", e), ("not", e),
# ("bin", op, left, right)


class ExprParser:
    def __init__(self, tokens, line, text, filename=None):
        self.tokens = tokens
        self.pos = 0
        self.line = line
        self.text = text
        self.filename = filename

    def fail(self, message, tok=None):
        if tok is None:
            tok = self.tokens[self.pos] if self.pos < len(self.tokens) \
                else None
        if tok is not None:
            raise AsmError(message, line=tok.line, col=tok.col,
                           source_line=self.text, filename=self.filename)
        raise AsmError(message, line=self.line, source_line=self.text,
                       filename=self.filename)

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) \
            else None

    def advance(self):
        tok = self.peek()
        self.pos += 1
        return tok

    def at_op(self, *ops):
        tok = self.peek()
        return tok is not None and tok.kind == "op" and tok.value in ops

    def parse(self):
        node = self.parse_or()
        if self.peek() is not None:
            self.fail(f"unexpected {self.peek().value!r} in expression")
        return node

    def parse_or(self):
        node = self.parse_xor()
        while self.at_op("|"):
            self.advance()
            node = ("bin", "|", node, self.parse_xor())
        return node

    def parse_xor(self):
        node = self.parse_and()
        while self.at_op("^"):
            self.advance()
            node = ("bin", "^", node, self.parse_and())
        return node

    def parse_and(self):
        node = self.parse_shift()
        while self.at_op("&"):
            self.advance()
            node = ("bin", "&", node, self.parse_shift())
        return node

    def parse_shift(self):
        node = self.parse_add()
        while self.at_op("<<", ">>"):
            op = self.advance().value
            node = ("bin", op, node, self.parse_add())
        return node

    def parse_add(self):
        node = self.parse_mul()
        while self.at_op("+", "-"):
            op = self.advance().value
            node = ("bin", op, node, self.parse_mul())
        return node

    def parse_mul(self):
        node = self.parse_unary()
        while self.at_op("*", "/", "%"):
            op = self.advance().value
            node = ("bin", op, node, self.parse_unary())
        return node

    def parse_unary(self):
        if self.at_op("-"):
            self.advance()
            return ("neg", self.parse_unary())
        if self.at_op("~"):
            self.advance()
            return ("not", self.parse_unary())
        if self.at_op("+"):
            self.advance()
            return self.parse_unary()
        return self.parse_primary()

    def parse_primary(self):
        tok = self.advance()
        if tok is None:
            self.fail("expected a value in expression")
        if tok.kind == "number":
            return ("num", tok.value)
        if tok.kind == "ident":
            return ("id", tok.value)
        if tok.kind == "lparen":
            node = self.parse_or()
            closing = self.advance()
            if closing is None or closing.kind != "rparen":
                self.fail("missing closing paren", tok)
            return node
        self.fail(f"unexpected {tok.value!r} in expression", tok)


def parse_expr(tokens, line, text, filename=None):
    """Parse a token list into an expression node."""
    return ExprParser(tokens, line, text, filename).parse()


def evaluate(node, symbols, pc=0, line=None, text=None, filename=None):
    """Evaluate an expression node to an int."""
    def fail(message):
        raise AsmError(message, line=line, source_line=text,
                       filename=filename)

    kind = node[0]
    if kind == "num":
        return node[1]
    if kind == "id":
        name = node[1]
        if name == "$":
            return pc
        if name in symbols:
            return symbols[name]
        fail(f"undefined symbol {name!r}")
    if kind == "neg":
        return -evaluate(node[1], symbols, pc, line, text, filename)
    if kind == "not":
        return ~evaluate(node[1], symbols, pc, line, text, filename)
    if kind == "bin":
        _, op, left, right = node
        lval = evaluate(left, symbols, pc, line, text, filename)
        rval = evaluate(right, symbols, pc, line, text, filename)
        if op == "+":
            return lval + rval
        if op == "-":
            return lval - rval
        if op == "*":
            return lval * rval
        if op == "/":
            if rval == 0:
                fail("division by zero")
            return lval // rval
        if op == "%":
            if rval == 0:
                fail("division by zero")
            return lval % rval
        if op == "&":
            return lval & rval
        if op == "|":
            return lval | rval
        if op == "^":
            return lval ^ rval
        if op == "<<":
            return lval << rval
        if op == ">>":
            return lval >> rval
        fail(f"unknown operator {op!r}")
    fail(f"bad expression node {node!r}")
