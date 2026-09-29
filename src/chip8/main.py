"""Command line interface for the chip-8 assembler.

Usage:
    python3 tools/asm/main.py [-o out.ch8] [-l out.lst] [-D NAME=VAL]... src.asm

Without -o, the output is the input name with .ch8 instead of .asm.
-D defines a symbol before assembly, e.g. -D SPEED=4.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from asm import Assembler, AsmError  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(prog="asm",
                                 description="chip-8 assembler")
    ap.add_argument("src", help="input .asm file")
    ap.add_argument("-o", "--output", default=None,
                    help="output .ch8 file")
    ap.add_argument("-l", "--listing", default=None,
                    help="write a listing file")
    ap.add_argument("-D", "--define", action="append", default=[],
                    metavar="NAME=VAL",
                    help="define a symbol (repeatable)")
    args = ap.parse_args(argv)

    asm = Assembler()
    for define in args.define:
        if "=" not in define:
            ap.error(f"bad -D {define!r}, want NAME=VAL")
        name, val = define.split("=", 1)
        try:
            asm.symbols[name] = int(val, 0)
        except ValueError:
            ap.error(f"bad value in -D {define!r}")

    try:
        data, listing = asm.assemble_file(args.src)
    except AsmError as e:
        print(e, file=sys.stderr)
        return 1

    out = args.output
    if out is None:
        base, _ = os.path.splitext(args.src)
        out = base + ".ch8"
    with open(out, "wb") as f:
        f.write(data)
    if args.listing:
        listing.write(args.listing)
        print(f"wrote {out} ({len(data)} bytes) + {args.listing}")
    else:
        print(f"wrote {out} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
