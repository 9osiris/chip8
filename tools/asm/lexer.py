"""Lexer for the chip-8 assembly language.

One line in, a list of tokens out. Comments start with ';' (ignored
inside strings and char literals). Numbers are decimal, 0x hex, 0b
binary, or 0o octal. 'A' is a char literal, "text" is a string (only
valid in DB). A leading '.' on a word is stripped: '.org' and 'org'
are the same directive.
"""

from .errors import AsmError


class Token:
    def __init__(self, kind, value, line, col):
        self.kind = kind      # ident, number, string, comma, colon,
        self.value = value    # lbracket, rbracket, lparen, rparen, op
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.kind}, {self.value!r}, {self.line}:{self.col})"


class LexedLine:
    def __init__(self, lineno, tokens, text):
        self.lineno = lineno
        self.tokens = tokens
        self.text = text


def _is_ident_start(ch):
    return ch.isalpha() or ch == "_" or ch == "@"


def _is_ident_char(ch):
    return ch.isalnum() or ch == "_" or ch == "@"


def _read_number(text, i, line, col, src):
    j = i
    while j < len(text) and (text[j].isalnum() or text[j] == "_"):
        j += 1
    word = text[i:j].replace("_", "")
    try:
        if word[:2].lower() == "0x":
            value = int(word, 16)
        elif word[:2].lower() == "0b":
            value = int(word, 2)
        elif word[:2].lower() == "0o":
            value = int(word, 8)
        else:
            value = int(word, 10)
    except ValueError:
        raise AsmError(f"bad number {word!r}", line=line, col=col,
                       source_line=src)
    return Token("number", value, line, col), j


_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0",
            "\\": "\\", "'": "'", '"': '"'}


def _read_char(text, i, line, col, src):
    # text[i] is the opening quote
    j = i + 1
    if j < len(text) and text[j] == "\\":
        esc = text[j + 1] if j + 1 < len(text) else ""
        if esc not in _ESCAPES:
            raise AsmError(f"bad escape '\\{esc}'", line=line, col=col,
                           source_line=src)
        value = ord(_ESCAPES[esc])
        j += 2
    elif j < len(text):
        value = ord(text[j])
        j += 1
    else:
        raise AsmError("unterminated char literal", line=line, col=col,
                       source_line=src)
    if j >= len(text) or text[j] != "'":
        raise AsmError("unterminated char literal", line=line, col=col,
                       source_line=src)
    return Token("number", value, line, col), j + 1


def _read_string(text, i, line, col, src):
    j = i + 1
    out = []
    while j < len(text) and text[j] != '"':
        if text[j] == "\\" and j + 1 < len(text):
            esc = text[j + 1]
            if esc not in _ESCAPES:
                raise AsmError(f"bad escape '\\{esc}'", line=line,
                               col=col, source_line=src)
            out.append(_ESCAPES[esc])
            j += 2
        else:
            out.append(text[j])
            j += 1
    if j >= len(text):
        raise AsmError("unterminated string", line=line, col=col,
                       source_line=src)
    return Token("string", "".join(out), line, col), j + 1


def lex_line(text, lineno, filename=None):
    """Lex one source line into tokens."""
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        col = i + 1
        if ch.isspace():
            i += 1
        elif ch == ";":
            break  # rest of the line is a comment
        elif ch == "." and i + 1 < n and _is_ident_start(text[i + 1]):
            # leading dot: directive marker, stripped
            j = i + 1
            while j < n and _is_ident_char(text[j]):
                j += 1
            tokens.append(Token("ident", text[i + 1:j], lineno, col))
            i = j
        elif _is_ident_start(ch):
            j = i
            while j < n and _is_ident_char(text[j]):
                j += 1
            tokens.append(Token("ident", text[i:j], lineno, col))
            i = j
        elif ch.isdigit():
            tok, i = _read_number(text, i, lineno, col, text)
            tokens.append(tok)
        elif ch == "'":
            tok, i = _read_char(text, i, lineno, col, text)
            tokens.append(tok)
        elif ch == '"':
            tok, i = _read_string(text, i, lineno, col, text)
            tokens.append(tok)
        elif ch == ",":
            tokens.append(Token("comma", ",", lineno, col))
            i += 1
        elif ch == ":":
            tokens.append(Token("colon", ":", lineno, col))
            i += 1
        elif ch == "[":
            tokens.append(Token("lbracket", "[", lineno, col))
            i += 1
        elif ch == "]":
            tokens.append(Token("rbracket", "]", lineno, col))
            i += 1
        elif ch == "(":
            tokens.append(Token("lparen", "(", lineno, col))
            i += 1
        elif ch == ")":
            tokens.append(Token("rparen", ")", lineno, col))
            i += 1
        elif text[i:i + 2] in ("<<", ">>"):
            tokens.append(Token("op", text[i:i + 2], lineno, col))
            i += 2
        elif ch in "+-*/%&|^~":
            tokens.append(Token("op", ch, lineno, col))
            i += 1
        elif ch == "$" and (i + 1 >= n or not text[i + 1].isalnum()):
            # bare $ means the current address
            tokens.append(Token("ident", "$", lineno, col))
            i += 1
        else:
            raise AsmError(f"unexpected character {ch!r}", line=lineno,
                           col=col, source_line=text, filename=filename)
    return tokens


def lex_source(src, filename=None):
    """Lex a whole source file into a list of LexedLine."""
    out = []
    for lineno, text in enumerate(src.splitlines(), 1):
        tokens = lex_line(text, lineno, filename)
        out.append(LexedLine(lineno, tokens, text))
    return out
