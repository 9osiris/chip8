"""Tests for the full assembler: lexer, expressions, macros, encoding,
listing output, and error cases with line numbers."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from asm import AsmError, Assembler, assemble, assemble_with_listing
from asm import expr as expr_mod
from asm import lexer as lexer_mod
from asm import parser as parser_mod

ROOT = os.path.join(os.path.dirname(__file__), "..")


def asm(src):
    return assemble(src, filename="test.asm")


def expect_error(src, fragment):
    try:
        asm(src)
    except AsmError as e:
        assert fragment in str(e), f"{fragment!r} not in {e}"
        return str(e)
    raise AssertionError(f"no error for {src!r}")


# -- compatibility with the checked-in roms ------------------------------

def test_assemble_bounce_byte_identical():
    src = open(os.path.join(ROOT, "roms", "bounce.asm")).read()
    want = open(os.path.join(ROOT, "roms", "bounce.ch8"), "rb").read()
    assert assemble(src) == want


def test_assemble_catch_byte_identical():
    src = open(os.path.join(ROOT, "roms", "catch.asm")).read()
    want = open(os.path.join(ROOT, "roms", "catch.ch8"), "rb").read()
    assert assemble(src) == want


def test_catch_pixel_label_points_at_real_data():
    # regression test: the old tiny assembler counted every DB operand
    # as two bytes, so the pixel label landed five bytes past the data
    # and the falling pixel was invisible. the new assembler must get
    # the label right.
    src = open(os.path.join(ROOT, "roms", "catch.asm")).read()
    data = assemble(src)
    op = (data[0x10] << 8) | data[0x11]  # LD I, pixel at 0x210
    assert op & 0xF000 == 0xA000
    addr = op & 0xFFF
    assert data[addr - 0x200] == 0x80  # the pixel byte itself


# -- lexer -----------------------------------------------------------------

def test_lexer_numbers():
    toks = lexer_mod.lex_line("LD V1, 0x10 + 0b101 + 0o17 + 42", 1)
    vals = [t.value for t in toks if t.kind == "number"]
    assert vals == [0x10, 0b101, 0o17, 42]


def test_lexer_char_and_string():
    toks = lexer_mod.lex_line("DB 'A', \"hi\"", 1)
    assert toks[1].kind == "number" and toks[1].value == 65
    assert toks[3].kind == "string" and toks[3].value == "hi"


def test_lexer_comment_and_case():
    toks = lexer_mod.lex_line("ld v1, 5 ; a comment", 3)
    assert [t.value for t in toks if t.kind == "ident"] == ["ld", "v1"]
    assert toks[0].line == 3


def test_lexer_directive_dot():
    toks = lexer_mod.lex_line(".org 0x300", 1)
    assert toks[0].kind == "ident" and toks[0].value == "org"


def test_lexer_operators():
    toks = lexer_mod.lex_line("DB 1 << 2 >> 3", 1)
    ops = [t.value for t in toks if t.kind == "op"]
    assert ops == ["<<", ">>"]


def test_lexer_errors():
    for bad in ['DB "oops', "DB 'ab'", "LD V1, 0xZZ", "JP ?"]:
        try:
            lexer_mod.lex_line(bad, 7)
        except AsmError as e:
            assert "7" in str(e)
            continue
        raise AssertionError(f"no lexer error for {bad!r}")


# -- expressions -------------------------------------------------------------

def _expr_value(src, symbols=None, pc=0x200):
    toks = lexer_mod.lex_line(src, 1)
    node = expr_mod.parse_expr(toks, 1, src)
    return expr_mod.evaluate(node, symbols or {}, pc=pc, line=1,
                             text=src)


def test_expr_precedence():
    assert _expr_value("1 + 2 * 3") == 7
    assert _expr_value("(1 + 2) * 3") == 9
    assert _expr_value("0xF0 & 0x3C | 0x03") == (0xF0 & 0x3C) | 0x03
    assert _expr_value("1 << 4 >> 1") == 8
    assert _expr_value("10 - 2 - 3") == 5
    assert _expr_value("17 / 5") == 3
    assert _expr_value("17 % 5") == 2
    assert _expr_value("~0x0F & 0xFF") == 0xF0
    assert _expr_value("-5 + 12") == 7
    assert _expr_value("1 ^ 1 ^ 2") == 2


def test_expr_symbols_and_dollar():
    syms = {"base": 0x300, "n": 4}
    assert _expr_value("base + n * 2", syms) == 0x308
    assert _expr_value("$", syms, pc=0x206) == 0x206
    assert _expr_value("$-4", syms, pc=0x206) == 0x202


def test_expr_errors():
    expect_error("LD V0, nosuchlabel", "undefined symbol")
    expect_error("LD V0, 1 / 0", "division by zero")
    expect_error("LD V0, 1 % 0", "division by zero")
    expect_error("LD V0, (1 + 2", "missing closing paren")


# -- basic encoding ------------------------------------------------------------

def test_encode_all_mnemonics():
    src = """
        CLS
        RET
        JP target
        CALL 0x300
    target:
        SE V1, 0x10
        SNE V1, V2
        SE V3, V4
        SNE V5, 0x20
        LD V6, 0xAB
        ADD V6, 1
        LD V7, V8
        ADD V9, VA
        OR VB, VC
        AND VD, VE
        XOR V0, V1
        SUB V2, V3
        SUBN V4, V5
        SHR V6
        SHL V7
        RND V8, 0x0F
        DRW V9, VA, 5
        SKP VB
        SKNP VC
        LD I, 0x300
        LD V0, DT
        LD V1, K
        LD DT, V2
        LD ST, V3
        ADD I, V4
        LD F, V5
        LD B, V6
        LD [I], V7
        LD V8, [I]
    """
    data = asm(src)
    words = [(data[i] << 8) | data[i + 1]
             for i in range(0, len(data), 2)]
    assert words[:2] == [0x00E0, 0x00EE]
    assert words[2] == 0x1200 | 8    # JP target (4th instr, addr 0x208)
    assert words[3] == 0x2300
    assert 0x3110 in words           # SE V1, 0x10
    assert 0x9120 in words           # SNE V1, V2
    assert 0x5340 in words           # SE V3, V4
    assert 0x4520 in words           # SNE V5, 0x20
    assert 0x66AB in words
    assert 0x7601 in words
    assert 0x8780 in words
    assert 0x89A4 in words
    assert 0x8BC1 in words
    assert 0x8DE2 in words
    assert 0x8013 in words
    assert 0x8235 in words
    assert 0x8457 in words
    assert 0x8606 in words
    assert 0x870E in words
    assert 0xC80F in words
    assert 0xD9A5 in words
    assert 0xEB9E in words
    assert 0xECA1 in words
    assert 0xA300 in words
    assert 0xF007 in words
    assert 0xF10A in words
    assert 0xF215 in words
    assert 0xF318 in words
    assert 0xF41E in words
    assert 0xF529 in words
    assert 0xF633 in words
    assert 0xF755 in words
    assert 0xF865 in words


def test_encode_schip_mnemonics():
    data = asm("""
        SCD 4
        SCR
        SCL
        EXIT
        LOW
        HIGH
        DRW V1, V2, 16
        LD HF, V3
        LD RPL, V4
        LD V5, RPL
    """)
    words = [(data[i] << 8) | data[i + 1]
             for i in range(0, len(data), 2)]
    assert words == [0x00C4, 0x00FB, 0x00FC, 0x00FD, 0x00FE, 0x00FF,
                     0xD120, 0xF330, 0xF475, 0xF585]


def test_forward_and_backward_labels():
    data = asm("""
        JP end
    start:
        LD V0, 1
        JP start
    end:
        LD V0, 2
    """)
    words = [(data[i] << 8) | data[i + 1]
             for i in range(0, len(data), 2)]
    assert words == [0x1206, 0x6001, 0x1202, 0x6002]


def test_equ_org_db_dw():
    data = asm("""
        SCORE EQU 0x300
        LD I, SCORE
        ORG 0x300
        DB 1, 2, "AB", 'C'
        DW 0x1234, SCORE + 1
    """)
    assert data[0:2] == bytes([0xA3, 0x00])
    assert data[2:7] == bytes([1, 2, 0x41, 0x42, 0x43])
    assert data[7:11] == bytes([0x12, 0x34, 0x03, 0x01])


def test_case_insensitive():
    assert asm("cls") == bytes([0x00, 0xE0])
    assert asm("Ld V1, 0x05") == bytes([0x61, 0x05])
    assert asm("dRw vA, Vb, 5") == bytes([0xDA, 0xB5])


# -- macros ----------------------------------------------------------------------

def test_macro_basic():
    data = asm("""
        TWICE MACRO reg
            ADD reg, 1
            ADD reg, 1
        ENDM
        TWICE V3
    """)
    assert data == bytes([0x73, 0x01, 0x73, 0x01])


def test_macro_expression_arg():
    data = asm("""
        SET2 MACRO r, val
            LD r, (val)
            ADD r, val + 1
        ENDM
        SET2 V2, 0x10 + 1
    """)
    assert data == bytes([0x62, 0x11, 0x72, 0x12])


def test_macro_local_labels():
    data = asm("""
        SPIN MACRO n
            LD V0, n
        @again:
            ADD V0, 255
            SNE V0, 0
            JP @again
        ENDM
        SPIN 3
        SPIN 4
    """)
    words = [(data[i] << 8) | data[i + 1]
             for i in range(0, len(data), 2)]
    # two expansions, each jumps to its own renamed local label
    assert words[0] == 0x6003
    assert words[3] == 0x1202  # JP @again__m1
    assert words[4] == 0x6004
    assert words[7] == 0x120A  # JP @again__m2


def test_macro_nested():
    data = asm("""
        INNER MACRO r
            LD r, 7
        ENDM
        OUTER MACRO r
            INNER r
            ADD r, 1
        ENDM
        OUTER V5
    """)
    assert data == bytes([0x65, 0x07, 0x75, 0x01])


def test_macro_errors():
    expect_error("TWICE MACRO r\nLD r, 1\nENDM\nTWICE",
                 "takes 1 arguments, got 0")
    expect_error("REC MACRO\nREC\nENDM\nREC", "recursive macro")
    expect_error("A MACRO\nB\nENDM\nB MACRO\nA\nENDM\nA",
                 "recursive macro")
    expect_error("M MACRO r\nLD r, 1\nENDM\nM V1, V2",
                 "takes 1 arguments, got 2")
    expect_error("M MACRO\nLD V0, 1\n", "without a matching ENDM")
    expect_error("ENDM", "without a matching MACRO")
    expect_error("M MACRO V0\nLD V0, 1\nENDM", "bad macro parameter")


# -- error cases -------------------------------------------------------------------

def test_error_line_numbers():
    msg = expect_error("LD V0, 1\nBOGUS V1\nLD V2, 3", "unknown mnemonic")
    assert "test.asm:2" in msg
    assert "BOGUS V1" in msg


def test_error_cases():
    expect_error("FROB V0", "unknown mnemonic")
    expect_error("LD V16, 1", "undefined symbol")  # V16 is not a register
    expect_error("LD V0", "takes 2 operands")
    expect_error("LD V0, V1, V2", "takes 2 operands")
    expect_error("JP", "takes 1 operands")
    expect_error("ADD 5, V0", "first operand must be Vx")
    expect_error("LD 5, 6", "first operand must be Vx")
    expect_error("DRW V0, V1", "takes 3 operands")
    expect_error("SKP 5", "takes one register")
    expect_error("DB V0", "DB takes numbers or strings")
    expect_error("DW V0", "DW takes numbers")
    expect_error("LD DT, 5", "takes a register")
    expect_error("LD K, V0", "cannot load into K")
    expect_error("loop:\nloop:\nCLS", "duplicate label")
    expect_error("X EQU 1\nX EQU 2", "duplicate symbol")
    expect_error("V0:\nCLS", "looks like a register")
    expect_error("LD V0,", "empty operand")
    expect_error("ORG", "takes exactly one operand")


def test_error_unterminated_macro_source():
    try:
        asm("M MACRO\n LD V0, 1\n")
    except AsmError as e:
        assert "ENDM" in str(e)
        return
    raise AssertionError("no error")


def test_program_too_big():
    expect_error("ORG 0xFFF\nLD V0, 1\nLD V0, 2", "does not fit")


# -- defines, listing, cli ---------------------------------------------------------

def test_define_flag():
    a = Assembler()
    a.symbols["SPEED"] = 4
    data, _ = a.assemble_text("LD V0, SPEED")
    assert data == bytes([0x60, 0x04])


def test_listing_output():
    data, text = assemble_with_listing("LD V1, 5\nloop:\nJP loop\n")
    assert data == bytes([0x61, 0x05, 0x12, 0x02])
    lines = text.splitlines()
    assert lines[0] == "0200: 61 05          LD V1, 5"
    assert lines[1] == "0202:                loop:"
    assert lines[2] == "0202: 12 02          JP loop"


def test_cli_writes_files():
    from asm.main import main
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "t.asm")
        open(src, "w").write("LD V2, 0x0A\n")
        out = os.path.join(d, "t.ch8")
        lst = os.path.join(d, "t.lst")
        assert main(["-o", out, "-l", lst, src]) == 0
        assert open(out, "rb").read() == bytes([0x62, 0x0A])
        assert "0200: 62 0A" in open(lst).read()
        # error path returns 1
        open(src, "w").write("BOGUS\n")
        assert main(["-o", out, src]) == 1


def test_cli_define():
    from asm.main import main
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "t.asm")
        open(src, "w").write("LD V0, SPEED\n")
        out = os.path.join(d, "t.ch8")
        assert main(["-o", out, "-D", "SPEED=9", src]) == 0
        assert open(out, "rb").read() == bytes([0x60, 0x09])
