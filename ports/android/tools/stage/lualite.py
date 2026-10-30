"""Read the arcade's data-only Lua files (car.lua, wheel_list.lua): top-level
`Name = expression` assignments of strings, numbers, tables, names and `..` joins.

usage: lualite.load(path) -> {name: value}; tables become dicts (keys) or lists (no keys).
"""
import re

TOKEN = re.compile(r'''
    (?P<space>\s+) |
    (?P<comment>--\[\[.*?\]\]|--[^\n]*) |
    (?P<str>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*') |
    (?P<num>-?\d+\.?\d*(?:[eE][-+]?\d+)?|-?\.\d+) |
    (?P<name>[A-Za-z_][A-Za-z0-9_]*) |
    (?P<op>\.\.|[{}\[\]=,;()])
''', re.S | re.X)


def tokens(text):
    pos = 0
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m:
            raise ValueError("bad Lua at %r" % text[pos:pos + 40])
        pos = m.end()
        kind = m.lastgroup
        if kind in ("space", "comment"):
            continue
        yield kind, m.group(kind)


class Parser:
    def __init__(self, text, env):
        self.t = list(tokens(text))
        self.i = 0
        self.env = env

    def peek(self, k=0):
        return self.t[self.i + k] if self.i + k < len(self.t) else (None, None)

    def take(self, value=None):
        tok = self.t[self.i]
        if value is not None and tok[1] != value:
            raise ValueError("expected %s, got %s" % (value, tok[1]))
        self.i += 1
        return tok

    def atom(self):
        kind, v = self.take()
        if kind == "str":
            return v[1:-1].encode("latin1", "backslashreplace").decode("unicode_escape").encode("latin1").decode("utf8")
        if kind == "num":
            return float(v) if any(c in v for c in ".eE") else int(v)
        if kind == "name":
            if v in ("true", "false"):
                return v == "true"
            if v == "nil":
                return None
            return self.env.get(v)
        if v == "{":
            return self.table()
        if v == "(":
            e = self.expr()
            self.take(")")
            return e
        raise ValueError("unexpected %s" % v)

    def expr(self):
        v = self.atom()
        while self.peek()[1] == "..":
            self.take()
            v = "%s%s" % (v, self.atom())
        return v

    def table(self):
        keyed, items = {}, []
        while self.peek()[1] != "}":
            if self.peek()[0] == "name" and self.peek(1)[1] == "=":
                k = self.take()[1]
                self.take("=")
                keyed[k] = self.expr()
            elif self.peek()[1] == "[":
                self.take()
                k = self.expr()
                self.take("]")
                self.take("=")
                keyed[k] = self.expr()
            else:
                items.append(self.expr())
            if self.peek()[1] in (",", ";"):
                self.take()
        self.take("}")
        if keyed and items:
            keyed.update({i + 1: v for i, v in enumerate(items)})
            return keyed
        return keyed if keyed or not items else items

    def chunk(self):
        while self.i < len(self.t):
            name = self.take()[1]
            self.take("=")
            self.env[name] = self.expr()
        return self.env


def load(path, env=None):
    return Parser(open(path, encoding="utf8", errors="replace").read(), dict(env or {})).chunk()
