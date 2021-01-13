# Helper classes, as you see fit.
import functools
import re
from typing import Any


class Expression:
    def __init__(self):
        self.tokens = []

    def __str__(self):
        return "".join(str(t) for t in self.tokens)

    def __eq__(self, other):
        return self.tokens == other.tokens

    def is_compound(self):
        return False

    def is_whitespace(self):
        return False

    def is_atom(self):
        return False

    def is_literal(self):
        return False

    def is_bool(self):
        return False

    def is_number(self):
        return False

    def is_string(self):
        return False

    def is_identifier(self):
        return False


class Compound(Expression):
    def __init__(self):
        self._children = []

    def __iter__(self):
        return iter(self._children)

    def __repr__(self):
        return f"Compound({self._children})"

    def append(self, exp):
        self._children.append(exp)

    def is_compound(self):
        return iter(self._children)


class Atom(Expression):
    def is_atom(self):
        return True


class Token:
    REGEX = ""
    def __init__(self, x: str):
        self.value: Any = None

    def __repr__(self):
        return f"{self.__class__.__name__}({self.value})"

    def __eq__(self, other):
        return self.value == other.value


@functools.total_ordering
class Number(Token, Atom):
    REGEX = r"[+-]?\d+(\.\d+)?"

    def __init__(self, x: str):
        try:
            self.value = int(x)
        except ValueError:
            self.value = float(x)
        self.real = self.value

    def __str__(self):
        return str(self.value)

    def __add__(self, other):
        return self.real + other.real

    def __sub__(self, other):
        return self.real - other.real

    def __mul__(self, other):
        return self.real * other.real

    def __truediv__(self, other):
        return self.real / other.real

    def __lt__(self, other):
        return self.real < other.real

    def __eq__(self, other):
        return self.real == other.real

    def __radd__(self, other):
        return self.real + other.real

    def __rsub__(self, other):
        return other.real - self.real

    def __rmul__(self, other):
        return self.real * other.real

    def __rtruediv__(self, other):
        return other.real / self.real

    def __int__(self):
        return int(self.value)

    def is_number(self):
        return True

    def is_literal(self):
        return True


class String(Token, Atom):
    REGEX = r'"(((\\\\)|(\\")|[^\\"])*)"'

    def __init__(self, x: str):
        m = re.fullmatch(self.REGEX, x)
        if m is not None:
            self.value = m.group(1)
        else:
            raise RuntimeError(f"Cannot tokenize {x}")

    def __str__(self):
        return "\"{}\"".format(self.value)

    def __len__(self):
        return len(self.value)

    def is_string(self):
        return True

    def is_literal(self):
        return True


class Boolean(Token, Atom):
    REGEX = r'(#f)|(#t)'

    def __init__(self, x: str):
        self.value = True if x == "#t" else False

    def __str__(self):
        return "#t" if self.value else "#f"

    def __bool__(self):
        return self.value

    def is_bool(self):
        return True

    def is_literal(self):
        return True


class Identifier(Token, Atom):
    initial_ID = r"a-z!$%&*/:<=>?^_~"
    next_ID = initial_ID+r"\d+\-.@#"
    REGEX = r"(["+initial_ID+r"]["+next_ID+r"]*)|[+-]"

    def __init__(self, x: str):
        self.value = x

    def __str__(self):
        return self.value

    def is_identifier(self):
        return True

class LPar(Token):
    REGEX = r"(\(|\[)"

    def __str__(self):
        return "("


class RPar(Token):
    REGEX = r"(\)|\])"

    def __str__(self):
        return ")"


class Whitespace(Token):
    REGEX = r"\s+"

    def __init__(self, x: str):
        self.value: str = x

    def __str__(self):
        return self.value


