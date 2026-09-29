"""Macro expansion.

A macro is invoked like an instruction whose mnemonic matches a macro
name. Arguments are substituted for parameters: a bare parameter used
as a whole operand is replaced by the whole argument operand, and a
parameter inside a bigger expression is replaced by the argument's
expression. Labels starting with '@' are local to the macro: each
expansion renames them with a unique suffix so a macro can be used
more than once. Recursive macro use is an error.
"""

import copy

from . import parser as parser_mod
from .errors import AsmError


def _rename_id(name, uid):
    return f"{name}__m{uid}" if name.startswith("@") else name


def _subst_node(node, args, ll_text, line, filename):
    # replace ("id", param) leaves with the argument's expression
    kind = node[0]
    if kind == "id":
        name = node[1]
        if name in args:
            arg = args[name]
            if arg[0] == "expr":
                return copy.deepcopy(arg[1])
            raise AsmError(
                f"parameter {name!r} is a register or keyword,"
                " it cannot appear inside an expression",
                line=line, source_line=ll_text, filename=filename)
        return ("id", _rename_id(name, args["_uid"]))
    if kind in ("neg", "not"):
        return (kind, _subst_node(node[1], args, ll_text, line, filename))
    if kind == "bin":
        return ("bin", node[1],
                _subst_node(node[2], args, ll_text, line, filename),
                _subst_node(node[3], args, ll_text, line, filename))
    return node


def _subst_operand(op, args, ll_text, line, filename):
    # a bare parameter as the whole operand becomes the whole argument
    if op[0] == "expr" and op[1][0] == "id" and op[1][1] in args:
        return copy.deepcopy(args[op[1][1]])
    if op[0] == "expr":
        return ("expr", _subst_node(op[1], args, ll_text, line, filename))
    if op[0] == "sym":
        return op
    return op


def _subst_stmt(stmt, args, uid, filename):
    args = dict(args)
    args["_uid"] = uid
    text, line = stmt.text, stmt.line
    if isinstance(stmt, parser_mod.Label):
        return parser_mod.Label(_rename_id(stmt.name, uid), line, text)
    if isinstance(stmt, parser_mod.Instr):
        ops = [_subst_operand(o, args, text, line, filename)
               for o in stmt.operands]
        return parser_mod.Instr(stmt.mnemonic, ops, line, text)
    if isinstance(stmt, parser_mod.Org):
        return parser_mod.Org(
            _subst_node(stmt.expr, args, text, line, filename), line, text)
    if isinstance(stmt, parser_mod.Db):
        items = []
        for kind, val in stmt.items:
            if kind == "expr":
                items.append(("expr", _subst_node(val, args, text, line,
                                                 filename)))
            else:
                items.append((kind, val))
        return parser_mod.Db(items, line, text)
    if isinstance(stmt, parser_mod.Dw):
        exprs = [_subst_node(e, args, text, line, filename)
                 for e in stmt.exprs]
        return parser_mod.Dw(exprs, line, text)
    if isinstance(stmt, parser_mod.Equ):
        name = stmt.name
        if name.startswith("@"):
            name = _rename_id(name, uid)
        return parser_mod.Equ(
            name,
            _subst_node(stmt.expr, args, text, line, filename), line, text)
    raise AsmError("cannot appear inside a macro",
                   line=line, source_line=text, filename=filename)


def expand_macro(macro, arg_operands, stmt, macros, stack, uidbox,
                 filename=None):
    """Expand one macro invocation into a statement list."""
    if len(arg_operands) != len(macro.params):
        raise AsmError(
            f"macro {macro.name} takes {len(macro.params)} arguments,"
            f" got {len(arg_operands)}",
            line=stmt.line, source_line=stmt.text, filename=filename)
    if macro.name in stack:
        raise AsmError(f"recursive macro {macro.name}",
                       line=stmt.line, source_line=stmt.text,
                       filename=filename)
    uidbox[0] += 1
    uid = uidbox[0]
    args = dict(zip(macro.params, arg_operands))
    expanded = [_subst_stmt(s, args, uid, filename) for s in macro.body]
    out = []
    _expand_list(expanded, macros, stack + [macro.name], uidbox,
                 filename, out)
    return out


def _expand_list(stmts, macros, stack, uidbox, filename, out):
    for stmt in stmts:
        if isinstance(stmt, parser_mod.Instr) \
                and stmt.mnemonic in macros:
            out.extend(expand_macro(macros[stmt.mnemonic],
                                    stmt.operands, stmt, macros, stack,
                                    uidbox, filename))
        else:
            out.append(stmt)


def expand_all(stmts, macros, filename=None):
    """Expand every macro invocation in a statement list."""
    out = []
    _expand_list(stmts, macros, [], [0], filename, out)
    return out
