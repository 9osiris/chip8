"""Backwards-compatible front end for the assembler.

Old usage still works:
    python3 tools/assemble.py roms/bounce.asm roms/bounce.ch8

For the new options (listing files, -D defines) use tools/asm/main.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from asm.main import main  # noqa: E402


def legacy(argv):
    # tools/assemble.py in.asm out.ch8 -> asm/main.py -o out.ch8 in.asm
    if len(argv) == 3 and not argv[1].startswith("-"):
        return main(["-o", argv[2], argv[1]])
    return main(argv[1:])


if __name__ == "__main__":
    sys.exit(legacy(sys.argv))
