# You can drop your parser from hw3 into this file, if you want to
# use it.

import re
from typing import Dict, List, Optional
from classes import *


def tokenize(x: str) -> List[Token]:
    def start(pattern: str, x: str):
        match = re.match(pattern, x)
        if match is None:
            return "", x
        if match.span()[0] == 0:
            return x[:match.span()[1]], x[match.span()[1]:]
        return "", x
    tokens = []
    while x:
        for sub in Token.__subclasses__():
            match, x = start(sub.REGEX, x)
            if match:
                tok = sub(match)
                if isinstance(tok, Whitespace):
                    tok.value = tok.value[0]
                tokens.append(tok)
                break
        else:
            raise RuntimeError(f"Cannot tokenize {x}.")
    return tokens

def matching_pars(tokens: List[Token]) -> Dict[int, int]:
    pars = []
    lefts = []
    for i, token in enumerate(tokens):
        if isinstance(token, LPar):
            lefts.append(i)
        if isinstance(token, RPar):
            try:
                pars.append((lefts.pop(), i))
            except IndexError:
                raise RuntimeError("Parentheses do not match.")
    if lefts:
        raise RuntimeError("Parentheses not properly closed.")
    return dict(pars)

def nest(tokens: List[Token],pars: Dict[int, int], start: int, end: int) -> Compound:
    exp = Compound()
    x = start
    while x < end:
        t = tokens[x]
        if isinstance(t, LPar):
            p = nest(tokens, pars, x+1, pars[x])
            p.tokens = tokens[x:pars[x]+1]
            exp.append(p)
            x = pars[x]
        if isinstance(t, Atom):
            exp.append(t)
        x += 1
    return exp


def parse(x: str) -> Optional[Expression]:
    try:
        tokens = tokenize(x)
        cleaned_tokens = [t for t in tokens if not isinstance(t, Whitespace)]
        pars = matching_pars(tokens)
    except RuntimeError:
        return None
    if not pars and len(cleaned_tokens) > 1:
        return None
    for pair in pars.items():
        if abs(pair[1] - pair[0]) == 1:
            return None
    if not cleaned_tokens:
        return None
    if not pars:
        if isinstance(cleaned_tokens[0], Atom):
            atom = cleaned_tokens[0]
            atom.tokens = tokens
            return atom
    nested = nest(tokens, pars, 1, len(tokens)-1)
    nested.tokens = tokens
    return nested

