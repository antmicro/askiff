from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar, Union

SCH_COLUMN_WIDTH = 71
PCB_COLUMN_WIDTH = 72


class Qstr(str):
    """Class for strings that should be quoted after serialization"""

    pass


class Sexpr(list[Union["Sexpr", str]]):
    __re_pattern: ClassVar = r"""
        # This `()` creates matching group it will match one of contained sub groups
        # retrieve matched string with match.group(1)
        (
            (?:
                # opening parentheses `(` - starts list
                \(

                # AND one or more ident (a-zA-Z0-9) or numerics
                # duplicating ident matching, reduces number of matches and speeds up
                [-.\s\w]+

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
            mp = m[0]
            if mp == "(":
                if m[-1] == ")":
                    out.append(Sexpr(m[1:-1].split()))
                else:
                    stack.append(out)
                    out = Sexpr()
                    out.extend(m[1:].split())
            elif mp == ")":
                if not stack:
                    raise AssertionError("Incorrect nesting of brackets")
                tmpout, out = out, stack.pop()
                out.append(tmpout)
            elif mp == "|":
                out.extend(m.split())
            elif mp == '"':
                # string (strip of `"` and remove escaped `\"`)
                out.append(Qstr(m[1:-1].replace(r"\"", r'"')))
            else:
                # ident or numeric
                out.append(m)
        if stack:
            raise AssertionError("Incorrect nesting of brackets")
        return out[0]  # type: ignore

    @staticmethod
    def from_file(path: Path) -> Sexpr:
        return Sexpr.from_str(path.read_text())

    def to_str(self, indent: int = 0, column_width: int = 71) -> str:
        se0, *se1 = self  # unload for perf
        ret = indent * "\t" + "(" + se0  # type: ignore

        inline = True
        indent_loc = indent + 1
        if se0 == "pts":
            inline = False
            max_len = 98 - indent_loc
            available_len = -1
            for s in se1:
                if s[0] == "xy":  # xy is quite common case, inline to speedup
                    xy_txt = f"(xy {s[1]} {s[2]})"
                    # xy_txt = "(xy " + s[1] + " " + s[2] + ")"
                else:
                    xy_txt = s.to_str(0, column_width)  # type: ignore
                xy_len = len(xy_txt)
                if available_len >= 0:
                    ret += " " + xy_txt
                    available_len -= xy_len + 1
                else:
                    ret += "\n" + indent_loc * "\t" + xy_txt
                    available_len = max_len - xy_len
        else:
            max_len = column_width - indent_loc
            available_len = max_len - 1 - len(se0)
            for s in se1:
                if isinstance(s, Qstr):
                    s = '"' + s.replace(r'"', r"\"") + '"'
                    str_len = len(s)
                    if available_len >= 0:
                        ret += " " + s
                        available_len -= str_len + 1
                    else:
                        ret += "\n" + indent_loc * "\t" + s
                        available_len = max_len - str_len
                        inline = False
                elif isinstance(s, str):
                    str_len = len(s)
                    if available_len >= 0:
                        ret += " " + s
                        available_len -= str_len + 1
                    else:
                        ret += "\n" + indent_loc * "\t" + s
                        available_len = max_len - str_len
                        inline = False
                else:
                    ret += "\n" + s.to_str(indent_loc, column_width)
                    inline = False
        if not inline:
            ret += "\n" + indent * "\t" + ")"
        else:
            ret += ")"

        return ret

    def to_file(self, path: Path) -> None:
        column_width = SCH_COLUMN_WIDTH if "sch" in path.suffix else PCB_COLUMN_WIDTH
        path.write_text(self.to_str(column_width=column_width) + "\n")
