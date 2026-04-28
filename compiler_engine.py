"""
Compiler Engine for RegexEdu

This module performs:
1. Tokenization
2. Rule-based parsing
3. AST generation
4. Regex generation
5. Regex optimization
6. DFA/NFA classification
7. Lab practice regex tasks
"""

import json

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# -----------------------------
# SYMBOL TABLES (PER PHASE)
# -----------------------------

_GRAMMAR_KEYWORDS = {
    # operators / rule words in the Pattern DSL grammar
    "and", "or",
    "starts", "start", "with",
    "ends", "end",
    "contains",
    "only",
}

_VALUE_KEYWORDS = {
    # tokens that are semantically "literals" (map to regex classes)
    "digit", "digits",
    "letter", "letters",
    "lowercase", "uppercase",
}


def _token_kind(tok: str) -> str:
    t = str(tok).lower()
    if t in _GRAMMAR_KEYWORDS:
        return "GRAMMAR_KEYWORD"
    if t in _VALUE_KEYWORDS:
        return "VALUE_KEYWORD"
    # very small heuristic: treat non-alpha tokens as literal-ish
    if any(ch in t for ch in r"+*?|^$()[]{}\ ".strip()):
        return "OPERATOR"
    return "IDENTIFIER"


def build_symbol_table_tokens(tokens: List[str]) -> Dict[str, Any]:
    """
    Symbol table for lexical phase.
    """
    entries = []
    for i, tok in enumerate(tokens):
        entries.append({
            "id": i,
            "lexeme": tok,
            "normalized": str(tok).lower(),
            "kind": _token_kind(tok),
        })
    return {
        "phase": "tokens",
        "columns": ["id", "lexeme", "normalized", "kind"],
        "entries": entries,
    }


def _ast_children(node: Any) -> List[Any]:
    if not isinstance(node, dict):
        return []
    out = []
    if "left" in node:
        out.append(node["left"])
    if "right" in node:
        out.append(node["right"])
    return out


def _ast_to_node_table(ast: Any) -> List[Dict[str, Any]]:
    """
    Produces stable node ids in pre-order traversal.
    """
    rows: List[Dict[str, Any]] = []
    next_id = 0

    def visit(node: Any, parent_id: Optional[int]) -> Optional[int]:
        nonlocal next_id
        if node is None:
            return None

        if isinstance(node, str):
            # try JSON (lab mode sometimes stores AST as a JSON string)
            try:
                node = json.loads(node)
            except Exception:
                nid = next_id
                next_id += 1
                rows.append({
                    "node_id": nid,
                    "parent_id": parent_id,
                    "node_type": "LITERAL",
                    "value": node,
                })
                return nid

        if not isinstance(node, dict):
            nid = next_id
            next_id += 1
            rows.append({
                "node_id": nid,
                "parent_id": parent_id,
                "node_type": type(node).__name__.upper(),
                "value": str(node),
            })
            return nid

        nid = next_id
        next_id += 1

        node_type = node.get("type") or node.get("rule") or "NODE"
        value = node.get("value")

        rows.append({
            "node_id": nid,
            "parent_id": parent_id,
            "node_type": node_type,
            "value": value,
        })

        for child in _ast_children(node):
            visit(child, nid)

        # lab ast extra fields
        for key in ("components",):
            if isinstance(node.get(key), list):
                for item in node[key]:
                    visit(item, nid)
        for key in ("start", "follow"):
            if node.get(key) is not None:
                visit(node[key], nid)

        return nid

    visit(ast, None)
    return rows


def build_symbol_table_ast(ast: Any) -> Dict[str, Any]:
    """
    Symbol table for parsing/AST phase.
    """
    entries = _ast_to_node_table(ast)
    return {
        "phase": "ast",
        "columns": ["node_id", "parent_id", "node_type", "value"],
        "entries": entries,
    }


def _safe_generate_regex(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        try:
            node = json.loads(node)
        except Exception:
            return str(node)
    if not isinstance(node, dict):
        return str(node)
    try:
        return generate_regex(node)
    except Exception:
        return ""


def build_symbol_table_regex(ast: Any, regex: str) -> Dict[str, Any]:
    """
    Symbol table for regex-generation phase.

    Each AST node becomes a "symbol" with the regex fragment it generates.
    """
    node_rows = _ast_to_node_table(ast)
    fragments = []

    # Re-walk AST in the same pre-order to attach fragments.
    # We rely on the same traversal ordering as _ast_to_node_table().
    idx = 0

    def visit(node: Any) -> None:
        nonlocal idx
        if node is None:
            return

        cur_idx = idx
        idx += 1

        frag = _safe_generate_regex(node)
        if cur_idx < len(node_rows):
            fragments.append({
                "node_id": node_rows[cur_idx]["node_id"],
                "node_type": node_rows[cur_idx]["node_type"],
                "value": node_rows[cur_idx].get("value"),
                "regex_fragment": frag,
            })

        if isinstance(node, str):
            try:
                node = json.loads(node)
            except Exception:
                return
        if not isinstance(node, dict):
            return

        for child in _ast_children(node):
            visit(child)
        if isinstance(node.get("components"), list):
            for item in node["components"]:
                visit(item)
        for key in ("start", "follow"):
            if node.get(key) is not None:
                visit(node[key])

    visit(ast)

    return {
        "phase": "regex",
        "columns": ["node_id", "node_type", "value", "regex_fragment"],
        "entries": fragments,
        "final_regex": regex,
    }


def optimize_regex_with_steps(regex: str) -> Tuple[str, List[Dict[str, Any]]]:
    steps: List[Dict[str, Any]] = []

    def apply_step(name: str, before: str, after: str, description: str) -> str:
        applied = before != after
        steps.append({
            "step": name,
            "description": description,
            "before": before,
            "after": after,
            "applied": applied,
        })
        return after

    def split_top_level_alternation(expr: str) -> Optional[List[str]]:
        """
        If expr is a top-level parenthesized alternation produced by our generator,
        return its alternatives. Otherwise return None.
        """
        s = (expr or "").strip()
        if len(s) < 2 or s[0] != "(" or s[-1] != ")":
            return None
        inner = s[1:-1]
        depth = 0
        parts: List[str] = []
        last = 0
        saw_bar = False
        for i, ch in enumerate(inner):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "|" and depth == 0:
                saw_bar = True
                parts.append(inner[last:i])
                last = i + 1
        if not saw_bar:
            return None
        parts.append(inner[last:])
        return [p for p in (x.strip() for x in parts) if p != ""]

    r0 = regex
    r1 = r0.replace(".*.*", ".*")
    r1 = apply_step(
        "collapse_dotstar",
        r0,
        r1,
        'Collapse repeated ".*.*" into ".*".',
    )

    r2 = r1.replace("++", "+")
    r2 = apply_step(
        "collapse_plus",
        r1,
        r2,
        'Collapse repeated "++" into "+".',
    )

    r3 = r2.replace("**", "*")
    r3 = apply_step(
        "collapse_star",
        r2,
        r3,
        'Collapse repeated "**" into "*".',
    )

    # Factor anchors over top-level OR: (^A|^B) -> ^(A|B)
    before = r3
    alts = split_top_level_alternation(before)
    after = before
    if alts and all(a.startswith("^") and len(a) > 1 for a in alts):
        stripped = [a[1:] for a in alts]
        after = "^(" + "|".join(stripped) + ")"
    r4 = apply_step(
        "factor_caret_over_or",
        before,
        after,
        'If every OR-branch begins with "^", factor it out: (^A|^B) → ^(A|B).',
    )

    # Factor $ over top-level OR: (A$|B$) -> (A|B)$
    before = r4
    alts = split_top_level_alternation(before)
    after = before
    if alts and all(a.endswith("$") and len(a) > 1 for a in alts):
        stripped = [a[:-1] for a in alts]
        after = "(" + "|".join(stripped) + ")$"
    r5 = apply_step(
        "factor_dollar_over_or",
        before,
        after,
        'If every OR-branch ends with "$", factor it out: (A$|B$) → (A|B)$.',
    )

    return r5, steps


def build_symbol_table_optimized(regex_before: str, regex_after: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Symbol table for optimization phase.
    """
    entries = []
    for i, s in enumerate(steps):
        entries.append({
            "id": i,
            "step": s.get("step"),
            "applied": s.get("applied"),
            "before": s.get("before"),
            "after": s.get("after"),
        })
    return {
        "phase": "optimized_regex",
        "columns": ["id", "step", "applied", "before", "after"],
        "entries": entries,
        "regex_before": regex_before,
        "regex_after": regex_after,
    }


# -----------------------------
# THOMPSON NFA (PATTERN MODE)
# -----------------------------

@dataclass
class _NFA:
    start: int
    accept: int
    transitions: List[Tuple[int, Optional[str], int]]  # (src, symbol or None for ε, dst)


class _NFABuilder:
    def __init__(self) -> None:
        self._next_state = 0
        self.transitions: List[Tuple[int, Optional[str], int]] = []

    def _new_state(self) -> int:
        s = self._next_state
        self._next_state += 1
        return s

    def _add(self, src: int, sym: Optional[str], dst: int) -> None:
        self.transitions.append((src, sym, dst))

    def _lit(self, sym: str) -> _NFA:
        s = self._new_state()
        a = self._new_state()
        self._add(s, sym, a)
        return _NFA(start=s, accept=a, transitions=[])

    def _eps(self) -> _NFA:
        s = self._new_state()
        a = self._new_state()
        self._add(s, None, a)
        return _NFA(start=s, accept=a, transitions=[])

    def _concat(self, left: _NFA, right: _NFA) -> _NFA:
        self._add(left.accept, None, right.start)
        return _NFA(start=left.start, accept=right.accept, transitions=[])

    def _or(self, left: _NFA, right: _NFA) -> _NFA:
        s = self._new_state()
        a = self._new_state()
        self._add(s, None, left.start)
        self._add(s, None, right.start)
        self._add(left.accept, None, a)
        self._add(right.accept, None, a)
        return _NFA(start=s, accept=a, transitions=[])

    def _star(self, inner: _NFA) -> _NFA:
        s = self._new_state()
        a = self._new_state()
        self._add(s, None, a)           # allow zero reps
        self._add(s, None, inner.start) # start inner
        self._add(inner.accept, None, inner.start)  # repeat
        self._add(inner.accept, None, a)            # exit
        return _NFA(start=s, accept=a, transitions=[])

    def _plus(self, inner: _NFA) -> _NFA:
        # A+ = A A*
        return self._concat(inner, self._star(self._clone_fragment(inner)))

    def _clone_fragment(self, frag: _NFA) -> _NFA:
        """
        Rebuild a fresh copy of a fragment by re-emitting its symbols.
        We only call this for simple literals/classes produced by _symbol_fragment().
        """
        # Fallback: treat as ε if something unexpected
        return self._eps()

    def _symbol_fragment(self, value: str) -> _NFA:
        """
        Convert a DSL literal into an NFA fragment that consumes characters.
        - If it's a mapped class like "[0-9]" treat as a single symbol token.
        - If it's a multi-character literal, emit a concatenation of characters.
        """
        rx = value_to_regex(value)
        if rx.startswith("[") and rx.endswith("]"):
            return self._lit(rx)
        # multi-char literal becomes concatenation of characters
        if len(rx) <= 1:
            return self._lit(rx)
        frag: Optional[_NFA] = None
        for ch in rx:
            part = self._lit(ch)
            frag = part if frag is None else self._concat(frag, part)
        return frag or self._eps()

    def _any_star(self) -> _NFA:
        # Σ* approximation for “any character” in the UI/DSL.
        return self._star(self._lit("ANY"))


def build_thompson_nfa_for_pattern_ast(ast: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a Thompson NFA for the *language semantics* of Pattern Mode rules.

    Note: In theory, every regex has an equivalent NFA and DFA. Here we show the NFA
    construction because it's the most direct to explain and visualize.
    """
    b = _NFABuilder()

    def compile_node(node: Dict[str, Any]) -> _NFA:
        t = node.get("type")

        if t == "START":
            base = b._symbol_fragment(node.get("value", ""))
            return b._concat(base, b._any_star())  # x Σ*

        if t == "END":
            base = b._symbol_fragment(node.get("value", ""))
            return b._concat(b._any_star(), base)  # Σ* x

        if t == "CONTAINS":
            base = b._symbol_fragment(node.get("value", ""))
            return b._concat(b._concat(b._any_star(), base), b._any_star())  # Σ* x Σ*

        if t == "ONLY":
            base = b._symbol_fragment(node.get("value", ""))
            # x+ (one or more)
            # implement plus without cloning complexity by building: x (x)*
            return b._concat(base, b._star(b._symbol_fragment(node.get("value", ""))))

        if t == "AND":
            left = compile_node(node["left"])
            right = compile_node(node["right"])
            # Mirrors generator: left .* right (i.e. left Σ* right)
            return b._concat(b._concat(left, b._any_star()), right)

        if t == "OR":
            left = compile_node(node["left"])
            right = compile_node(node["right"])
            return b._or(left, right)

        raise ValueError(f"Unsupported AST node for NFA: {t}")

    frag = compile_node(ast)

    # Emit a clean table; include ε as "ε" and ANY as Σ in UI description.
    transitions = [
        {"from": s, "symbol": ("ε" if sym is None else sym), "to": d}
        for (s, sym, d) in b.transitions
    ]
    state_count = b._next_state

    return {
        "note": "Theory note: Every regular expression has an equivalent NFA and an equivalent DFA.",
        "kind": "Thompson NFA",
        "state_count": state_count,
        "start_state": frag.start,
        "accept_state": frag.accept,
        "transitions": transitions,
        "legend": {
            "ε": "epsilon transition (consumes no input)",
            "ANY": "any single character (used to model Σ for start/end/contains rules)",
        },
    }


# -----------------------------
# TOKENIZATION
# -----------------------------

def tokenize(text):
    """
    Break input into tokens
    """
    text = text.lower().replace(",", "")
    tokens = text.split()
    return tokens


# -----------------------------
# VALUE → REGEX MAPPING
# -----------------------------

def value_to_regex(value):

    mapping = {

        "digit": "[0-9]",
        "digits": "[0-9]",

        "letter": "[a-zA-Z]",
        "letters": "[a-zA-Z]",

        "lowercase": "[a-z]",
        "uppercase": "[A-Z]"
    }

    return mapping.get(value, value)


# -----------------------------
# GRAMMAR + PARSER (RECURSIVE DESCENT)
# -----------------------------

PATTERN_GRAMMAR = r"""
Grammar (EBNF-ish) for Pattern Mode:

  expr        := or_expr
  or_expr     := and_expr ( "or" and_expr )*
  and_expr    := primary ( "and" primary )*
  primary     := start_rule | end_rule | contains_rule | only_rule

  start_rule    := ("starts" | "start") "with" literal
  end_rule      := ("ends" | "end") "with" literal
  contains_rule := "contains" literal
  only_rule     := "only" literal

  literal     := IDENTIFIER

Notes:
- Operator precedence: AND binds tighter than OR.
- This is intentionally a tiny DSL designed for predictable parsing in a demo.
"""


@dataclass(frozen=True)
class PatternToken:
    kind: str  # KEYWORD | IDENTIFIER | EOF
    lexeme: str


def _lex_pattern(tokens: List[str]) -> List[PatternToken]:
    out: List[PatternToken] = []
    for t in tokens:
        k = _token_kind(t)
        if k == "OPERATOR":
            # pattern DSL doesn't use regex operators; treat as identifier literal
            k = "IDENTIFIER"
        out.append(PatternToken(kind=k, lexeme=str(t).lower()))
    out.append(PatternToken(kind="EOF", lexeme=""))
    return out


class _PatternParser:
    def __init__(self, raw_tokens: List[str]):
        self.tokens = _lex_pattern(raw_tokens)
        self.i = 0
        # Reserved words for the DSL grammar itself (operators / rule words).
        # Other "keywords" like digit/letters/lowercase are treated as literal values.
        self._reserved = {
            "and", "or",
            "starts", "start", "with",
            "ends", "end",
            "contains",
            "only",
        }

    def _peek(self) -> PatternToken:
        return self.tokens[self.i]

    def _eat_lexeme(self, lexeme: str) -> PatternToken:
        tok = self._peek()
        if tok.lexeme != lexeme:
            raise ValueError(f'Expected "{lexeme}" but found "{tok.lexeme or "EOF"}".')
        self.i += 1
        return tok

    def _eat_identifier(self) -> str:
        tok = self._peek()
        if not tok.lexeme:
            raise ValueError('Expected a literal value but found "EOF".')
        # Allow DSL literal values to be either IDENTIFIER or KEYWORD, as long as
        # they are not reserved grammar words (e.g. "digit" is a valid literal).
        if tok.kind not in ("IDENTIFIER", "VALUE_KEYWORD", "GRAMMAR_KEYWORD") or tok.lexeme in self._reserved:
            raise ValueError(f'Expected a literal value but found "{tok.lexeme}".')
        self.i += 1
        return tok.lexeme

    def parse(self) -> Dict[str, Any]:
        ast = self._parse_or()
        if self._peek().kind != "EOF":
            raise ValueError(f'Unexpected token "{self._peek().lexeme}".')
        return ast

    def _parse_or(self) -> Dict[str, Any]:
        node = self._parse_and()
        while self._peek().lexeme == "or":
            self._eat_lexeme("or")
            rhs = self._parse_and()
            node = {"type": "OR", "left": node, "right": rhs}
        return node

    def _parse_and(self) -> Dict[str, Any]:
        node = self._parse_primary()
        while self._peek().lexeme == "and":
            self._eat_lexeme("and")
            rhs = self._parse_primary()
            node = {"type": "AND", "left": node, "right": rhs}
        return node

    def _parse_primary(self) -> Dict[str, Any]:
        t = self._peek().lexeme

        if t in ("starts", "start"):
            self.i += 1
            self._eat_lexeme("with")
            lit = self._eat_identifier()
            return {"type": "START", "value": lit}

        if t in ("ends", "end"):
            self.i += 1
            self._eat_lexeme("with")
            lit = self._eat_identifier()
            return {"type": "END", "value": lit}

        if t == "contains":
            self.i += 1
            lit = self._eat_identifier()
            return {"type": "CONTAINS", "value": lit}

        if t == "only":
            self.i += 1
            lit = self._eat_identifier()
            return {"type": "ONLY", "value": lit}

        raise ValueError(f'Invalid pattern. Expected a rule keyword but found "{t or "EOF"}".')


def parse_pattern(tokens: List[str]) -> Dict[str, Any]:

    """
    Parse tokens using a tiny formal grammar (recursive descent).
    """
    return _PatternParser(tokens).parse()


# -----------------------------
# REGEX GENERATION
# -----------------------------

def generate_regex(ast):

    node_type = ast["type"]

    # START
    if node_type == "START":
        return f"^{value_to_regex(ast['value'])}"

    # END
    if node_type == "END":
        return f"{value_to_regex(ast['value'])}$"

    # CONTAINS
    if node_type == "CONTAINS":
        return value_to_regex(ast["value"])

    # ONLY
    if node_type == "ONLY":
        return f"^{value_to_regex(ast['value'])}+$"

    # AND
    if node_type == "AND":

        left_regex = generate_regex(ast["left"])
        right_regex = generate_regex(ast["right"])

        return f"{left_regex}.*{right_regex}"

    # OR
    if node_type == "OR":

        left_regex = generate_regex(ast["left"])
        right_regex = generate_regex(ast["right"])

        return f"({left_regex}|{right_regex})"

    return ""


# -----------------------------
# REGEX OPTIMIZATION
# -----------------------------

def optimize_regex(regex):

    optimized, _steps = optimize_regex_with_steps(regex)
    return optimized


# -----------------------------
# DFA / NFA CLASSIFICATION
# -----------------------------

def classify(regex):

    if "|" in regex:
        return "NFA"

    return "DFA"


# -----------------------------
# LAB PRACTICE TASKS
# -----------------------------

LAB_TASKS = {

    "valid identifier": {
        "regex": r"^[A-Za-z_][A-Za-z0-9_]*$",
        "ast": {
            "rule": "IDENTIFIER",
            "start": "LETTER_OR_UNDERSCORE",
            "follow": "LETTER_DIGIT_UNDERSCORE*"
        }
    },

    "valid email": {
        "regex": r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$",
        "ast": {
            "rule": "EMAIL_PATTERN",
            "components": ["username", "@", "domain", ".", "tld"]
        }
    },

    "number literals": {
        # matches integers or decimals (optionally signed, optional exponent)
        "regex": r"-?(?:\d+\.\d+|\d+)(?:[eE][+-]?\d+)?",
        "ast": {
            "rule": "NUMBER_LITERAL",
            "components": ["sign?", "int_or_decimal", "exponent?"]
        }
    },

    "string literals": {
        # double-quoted strings supporting escape sequences like \" and \n
        "regex": r"\"(?:\\.|[^\"\\])*\"",
        "ast": {
            "rule": "STRING_LITERAL",
            "start": "\"",
            "follow": "(escaped_char | non_quote_char)* + \""
        }
    },

    "ipv4 address": {
        "regex": r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b",
        "ast": {
            "rule": "IPV4_ADDRESS",
            "components": ["octet", ".", "octet", ".", "octet", ".", "octet"]
        }
    },

    "palindromes (3 or 5)": {
        # 3-char palindrome: aba ; 5-char palindrome: abcba
        "regex": r"\b([A-Za-z])([A-Za-z])\1\b|\b([A-Za-z])([A-Za-z])[A-Za-z]\4\3\b",
        "ast": {
            "rule": "PALINDROME_3_OR_5",
            "components": ["len=3: (a)(b)\\1", "len=5: (a)(b)(c)\\2\\1"]
        }
    },

    "binary string": {
        "regex": r"^[01]+$",
        "ast": {
            "rule": "BINARY_STRING"
        }
    },

    "string ending with 0110": {
        "regex": r"0110$",
        "ast": {
            "rule": "ENDS_WITH_PATTERN"
        }
    },

    "remove vowels": {
        "regex": r"[aeiouAEIOU]",
        "ast": {
            "rule": "REMOVE_VOWELS"
        }
    }

}

LAB_ALIASES = {
    # UI lab-card prompts -> canonical LAB_TASKS keys
    "match all valid email addresses": "valid email",
    "valid email addresses": "valid email",
    "email validator": "valid email",

    "match integers and floating point numbers": "number literals",
    "number literals": "number literals",

    "match identifiers that start with a letter followed by letters or digits": "valid identifier",
    "valid identifier": "valid identifier",
    "identifiers": "valid identifier",

    "match strings enclosed in double quotes with escape sequences": "string literals",
    "string literals": "string literals",

    "match valid ipv4 addresses with four octets between 0 and 255": "ipv4 address",
    "ipv4 address": "ipv4 address",

    "match words that are palindromes of length 3 or 5": "palindromes (3 or 5)",
    "palindromes": "palindromes (3 or 5)",
}


# -----------------------------
# LAB MODE PROCESSOR
# -----------------------------

def process_lab(text):

    raw = (text or "").strip().lower()
    key = LAB_ALIASES.get(raw, raw)

    if key not in LAB_TASKS:
        raise ValueError("Task not supported")

    task = LAB_TASKS[key]

    regex = task["regex"]
    tokens = [key]
    ast = json.dumps(task["ast"], indent=2)
    optimized, steps = optimize_regex_with_steps(regex)

    return {

        "tokens": tokens,

        "ast": ast,

        "regex": regex,

        "optimized_regex": optimized,

        "classification": classify(optimized),

        "symbol_tables": {
            "tokens": build_symbol_table_tokens(tokens),
            "ast": build_symbol_table_ast(ast),
            "regex": build_symbol_table_regex(ast, regex),
            "optimized_regex": build_symbol_table_optimized(regex, optimized, steps),
        }

    }


# -----------------------------
# PATTERN MODE PROCESSOR
# -----------------------------

def process_pattern(text):

    tokens = tokenize(text)

    ast = parse_pattern(tokens)

    regex = generate_regex(ast)

    optimized, opt_steps = optimize_regex_with_steps(regex)

    return {

        "tokens": tokens,

        "ast": ast,

        "regex": regex,

        "optimized_regex": optimized,

        # Keep DB storage safe: `Conversion.classification` is String(20) in MySQL schema.
        # Correct theory statement is shown in UI: regex has equivalent NFA and DFA.
        "classification": "REGULAR",
        "automata": {
            "note": "Theory note: Every regular expression has an equivalent NFA and an equivalent DFA (same expressive power). This project focuses on showing the compiler pipeline.",
        },

        "symbol_tables": {
            "tokens": build_symbol_table_tokens(tokens),
            "ast": build_symbol_table_ast(ast),
            "regex": build_symbol_table_regex(ast, regex),
            "optimized_regex": build_symbol_table_optimized(regex, optimized, opt_steps),
        }

    }


# -----------------------------
# MAIN ENGINE ENTRY
# -----------------------------

def process_input(text, mode="pattern"):

    if mode == "pattern":
        return process_pattern(text)

    if mode == "lab":
        out = process_lab(text)
        # Keep it correct: lab tasks are pre-defined patterns (not built from our Pattern DSL AST),
        # so we do not claim Thompson construction here.
        out["classification"] = "REGULAR"
        out["automata"] = {
            "note": "Theory note: Every regex has an equivalent NFA and an equivalent DFA (same expressive power).",
        }
        return out

    raise ValueError("Invalid mode")