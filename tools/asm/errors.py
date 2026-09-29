"""Assembler errors with line numbers and source context."""


class AsmError(Exception):
    def __init__(self, message, line=None, col=None, source_line=None,
                 filename=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col
        self.source_line = source_line
        self.filename = filename

    def __str__(self):
        loc = ""
        if self.filename is not None:
            loc += f"{self.filename}:"
        if self.line is not None:
            loc += f"{self.line}:"
            if self.col is not None:
                loc += f"{self.col}:"
        head = f"{loc} error: {self.message}" if loc else \
            f"error: {self.message}"
        if self.source_line:
            caret = ""
            if self.col is not None:
                caret = "\n  " + " " * (self.col - 1) + "^"
            return f"{head}\n  {self.source_line.rstrip()}{caret}"
        return head


def error_at(message, token=None, line=None, text=None, filename=None):
    """Build an AsmError from a token or an explicit line number."""
    if token is not None:
        return AsmError(message, line=token.line, col=token.col,
                        source_line=text, filename=filename)
    return AsmError(message, line=line, source_line=text, filename=filename)
