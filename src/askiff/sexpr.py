from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar, Union

SCH_COLUMN_WIDTH = 71
PCB_COLUMN_WIDTH = 72
MAX_PTS_LINE_LENGTH = 98


class Qstr(str):
    """Class for strings that should be quoted after serialization"""

    pass


class Sexpr(list[Union["GeneralizedSexpr", str]]):
    __re_pattern: ClassVar = r"""
        # This `()` creates matching group it will match one of contained sub groups
        # retrieve matched string with match.group(1)
        (
            (?:
                # opening parentheses `(` - starts list
                \(

                # AND one or more ident (a-zA-Z0-9) or numerics
                # duplicating ident matching, reduces number of matches and speeds up
                [-.\s\w]*

                \)?
            ) |

            # OR closing parentheses `)` - ends list
            (?:\)) |

            # OR Non-quoted string (ident, numeric)
            (?:[-.\w]+) |

            # OR Quoted string
            (?:
                # opening quote
                "

                # AND 0 or more of
                (?:
                    (?:\\") | # `\"` (escaped quote)
                    [^"]      # OR any character except `"`
                    
                )*

                # AND closing quote
                "
            ) |

            # OR data block: | ... |
            (?:
                # opening sign
                [|]

                # AND 0 or more of
                [^|]*      # any character except `|`

                # AND closing sign
                [|]
            )
        )
    """

    @staticmethod
    def from_str(txt: str) -> Sexpr:
        stack = []
        out = Sexpr()
        # Iter over all regex pattern matches
        # re.VERBOSE - allows spaces, newlines and comments in pattern string
        for m in re.findall(Sexpr.__re_pattern, txt, re.VERBOSE):
            match m[0]:
                case "(":
                    if m[-1] == ")":
                        out.append(m[1:-1].split())
                    else:
                        stack.append(out)
                        out = m[1:].split()
                case ")":
                    if not stack:
                        raise AssertionError("Incorrect nesting of brackets")
                    tmpout, out = out, stack.pop()
                    out.append(tmpout)
                case "|":
                    out.extend(m.split())
                case '"':
                    # string (strip of `"` and remove escaped `\"`)
                    out.append(Qstr(m[1:-1].replace(r"\"", r'"')))
                case _:
                    # ident or numeric
                    out.append(m)
        if stack:
            raise AssertionError("Incorrect nesting of brackets")
        return Sexpr(out[0])

    @staticmethod
    def from_file(path: Path) -> Sexpr:
        return Sexpr.from_str(path.read_text())

    def to_file(self, path: Path) -> None:
        column_width = PCB_COLUMN_WIDTH if "pcb" in path.suffix else SCH_COLUMN_WIDTH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(to_str(self, column_width=column_width) + "\n")

    def serialize(self) -> GeneralizedSexpr:
        # This is stub for usage of Sexpr as fallback for unknown nodes
        return self

    def deserialize(self) -> GeneralizedSexpr:
        # This is stub for usage of Sexpr as fallback for unknown nodes
        return Sexpr(self)


GeneralizedSexpr = Sequence[Union["GeneralizedSexpr", str]]


def to_str(sexpr: GeneralizedSexpr, indent: int = 0, column_width: int = SCH_COLUMN_WIDTH) -> str:
    se0, *se1 = sexpr  # unload for perf

    inline = True
    indent_loc = indent + 1
    if se0 == "pts":
        ret = indent * "\t" + "(pts"
        inline = False
        max_len = MAX_PTS_LINE_LENGTH - indent_loc
        available_len = -1
        for s in se1:
            if s[0] == "xy":  # xy is quite common case, inline to speedup
                xy_txt = f"(xy {s[1]} {s[2]})"
                xy_len = len(xy_txt)
                if available_len >= 0:
                    ret += " " + xy_txt
                    available_len -= xy_len + 1
                else:
                    ret += "\n" + indent_loc * "\t" + xy_txt
                    available_len = max_len - xy_len
            else:
                ret += "\n" + to_str(s, indent_loc, column_width)
                available_len = max_len
        return ret + "\n" + indent * "\t" + ")"

    if not isinstance(se0, str):
        raise TypeError(f"First element of S-Expr node is expected to be a string! {se0} of {sexpr}")

    # there is one case in kicad files (jumper_pad_groups) where first item is quoted
    ser_first = ('"' + se0.replace(r'"', r"\"") + '"') if isinstance(se0, Qstr) else se0
    ret = indent * "\t" + "(" + ser_first
    max_len = column_width - indent_loc
    available_len = max_len - 1 - len(ser_first)
    for s in se1:
        if isinstance(s, str):
            if isinstance(s, Qstr):
                s = '"' + s.replace(r'"', r"\"") + '"'
            if available_len >= 0:
                ret += " " + s
                available_len -= len(s) + 1
            else:
                ret += "\n" + indent_loc * "\t" + s
                available_len = max_len - len(s)
                inline = False
        else:
            ret += "\n" + to_str(s, indent_loc, column_width)
            inline = False
    if inline:
        return ret + ")"
    return ret + "\n" + indent * "\t" + ")"
