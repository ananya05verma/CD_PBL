# RegexEdu — Mini Compiler Design Learning Tool (DSL → Regex)

RegexEdu is an educational mini “compiler/translator” project that shows how compiler phases work using a tiny English-like **Pattern DSL** that gets translated into a **Regular Expression (regex)**. It is designed for college compiler-design demos: enter a pattern, then view tokens, parsing/AST, generated regex, optimization trace, and a beginner-friendly automata/theory section.

---

## What this project demonstrates (compiler mapping)

- **Lexical Analysis (Tokenization)**: Input text → tokens (words). Token kinds are shown (grammar keywords vs value words vs identifiers).
- **Syntax Analysis (Parsing)**: Pattern Mode uses a **formal grammar** + **recursive descent parser** with correct precedence (**AND > OR**).
- **Intermediate Representation (AST)**: Parser produces an AST (`START`, `END`, `ONLY`, `CONTAINS`, `AND`, `OR`). AST is also shown as a phase symbol table (node table).
- **Code Generation**: AST → regex.
- **Optimization**: Regex rewrite rules are applied with a step-by-step trace (`applied: true/false`).
- **Automata**:
  - **Theory**: Every regex defines a regular language and has an equivalent **NFA** and an equivalent **DFA** (same expressive power).
  - The UI intentionally shows a simple “regex features used” checklist instead of full DFA/NFA transition tables.

---

## Modes

### Pattern Mode (English-like DSL)
Examples you can try:
- `starts with digit`
- `only letters`
- `starts with a and ends with z`
- `starts with a or starts with b`

Value mapping examples:
- `digit` → `[0-9]`
- `letters` → `[a-zA-Z]`
- `lowercase` → `[a-z]`
- `uppercase` → `[A-Z]`

### Lab Mode (Practice tasks)
Includes preset tasks such as:
- valid identifier
- valid email
- number literals
- string literals
- ipv4 address
…and more.

---
