"""Full chip-8 assembler: lexer, parser, macros, expressions, listing.

Quick use:
    from asm import assemble
    data = assemble(open("roms/bounce.asm").read())
"""

from .assembler import Assembler
from .errors import AsmError


def assemble(src, filename="<input>"):
    """Assemble source text, return the raw bytes."""
    data, _listing = Assembler().assemble_text(src, filename)
    return data


def assemble_with_listing(src, filename="<input>"):
    """Assemble source text, return (bytes, listing_text)."""
    data, listing = Assembler().assemble_text(src, filename)
    return data, listing.render()


__all__ = ["Assembler", "AsmError", "assemble", "assemble_with_listing"]
