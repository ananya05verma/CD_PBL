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

from typing import Any, Dict, List, Optional, Tuple


# -----------------------------
# SYMBOL TABLES (PER PHASE)
# -----------------------------

_KEYWORDS = {
    "and", "or",
    "starts", "start", "with",
    "ends", "end",
    "contains",
    "only",
    "digit", "digits",
    "letter", "letters",
    "lowercase", "uppercase",
}


def _token_kind(tok: str) -> str:
    t = str(tok).lower()
    if t in _KEYWORDS:
        return "KEYWORD"
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

    return r3, steps


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
# RULE BASED GRAMMAR PARSER
# -----------------------------

def parse_pattern(tokens):

    """
    Parse tokens using predefined grammar
    """

    # AND condition
    if "and" in tokens:

        idx = tokens.index("and")

        left = tokens[:idx]
        right = tokens[idx+1:]

        return {
            "type": "AND",
            "left": parse_pattern(left),
            "right": parse_pattern(right)
        }

    # OR condition
    if "or" in tokens:

        idx = tokens.index("or")

        left = tokens[:idx]
        right = tokens[idx+1:]

        return {
            "type": "OR",
            "left": parse_pattern(left),
            "right": parse_pattern(right)
        }

    # START rule
    if tokens[:2] == ["starts", "with"] or tokens[:2] == ["start", "with"]:

        return {
            "type": "START",
            "value": tokens[2]
        }

    # END rule
    if tokens[:2] == ["ends", "with"] or tokens[:2] == ["end", "with"]:

        return {
            "type": "END",
            "value": tokens[2]
        }

    # CONTAINS rule
    if tokens[0] == "contains":

        return {
            "type": "CONTAINS",
            "value": tokens[1]
        }

    # ONLY rule
    if tokens[0] == "only":

        return {
            "type": "ONLY",
            "value": tokens[1]
        }

    raise ValueError("Invalid grammar pattern")


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

        "classification": classify(optimized),

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
        return process_lab(text)

    raise ValueError("Invalid mode")