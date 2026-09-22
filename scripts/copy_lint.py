"""Copy lint: fail when text people read or hear contains a banned word.

Tier 1 (fails)
  - apps/web/src: string literals and JSX text (including lib/copy.ts)
  - apps/api: user-facing constants in main.py, auth.py, report_service.py,
    verdict_service.py, interviewer_service.py and planner_service.py questions
  - Interviewer and Verdict prompts (text between "copy-lint: off/on" markers
    is skipped, because it names the words it forbids)
Soft-avoid words only warn, with a suggested replacement.
Tier 2 (internal reasoning prompts, docs, logs, internal exceptions) is not scanned.

Usage: python scripts/copy_lint.py [--quiet]
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.copy_guard import find_banned, find_soft  # noqa: E402

WEB_SRC = ROOT / "apps" / "web" / "src"
PROMPTS = [
    ROOT / "apps/api/app/prompts/interviewer/v1.md",
    ROOT / "packages/prompts/interviewer/v1.md",
    ROOT / "apps/api/app/prompts/verdict/v1.md",
]
PY_FILES = [
    "main.py",
    "auth.py",
    "report_service.py",
    "verdict_service.py",
    "interviewer_service.py",
]
# Admin-only responses are internal, not copy for people practicing.
ADMIN_ONLY = {"Admin access required", "Skeptic inspection is temporarily unavailable"}

# Attributes whose values are identifiers or styling, never copy.
NON_COPY_ATTR = re.compile(
    r"""\b(?:className|id|htmlFor|href|key|type|role|name|rel|target|autoComplete|inputMode|"""
    r"""data-[\w-]+|aria-(?:labelledby|describedby|live|controls|current|pressed|selected|"""
    r"""valuemin|valuemax|valuenow|busy|hidden)|viewBox|fill|stroke\w*|width|height|d|"""
    r"""strokeLinecap|strokeOpacity|cx|cy|r|accept|encType|method|src|sizes|as)\s*=\s*("[^"]*"|'[^']*'|\{[^}]*\})"""
)
STRING_RE = re.compile(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'|`((?:[^`\\]|\\.)*)`')
JSX_TEXT_RE = re.compile(r">([^<>{}]+)<")
PLAIN_TEXT_LINE = re.compile(r"^[A-Za-z&][^<>{}=;()`]*$")


def has_words(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]{2,}\s+[A-Za-z]", text))


def web_copy(path: Path):
    """Yield (line, text) pairs for user-facing strings in a TS/TSX file."""
    in_block = False
    is_copy_file = path.name == "copy.ts"
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if in_block:
            if "*/" in line:
                in_block = False
            continue
        if line.startswith("/*") or line.startswith("{/*"):
            if "*/" not in line:
                in_block = True
            continue
        if line.startswith(("//", "*", "import ", "export type ", "type ")):
            continue
        code = re.sub(r"\s//.*$", "", raw)
        code = NON_COPY_ATTR.sub("", code)
        for match in STRING_RE.finditer(code):
            text = re.sub(r"\$\{[^}]*\}", "X", next(group for group in match.groups() if group is not None))
            if has_words(text) or (is_copy_file and text.strip()):
                yield number, text
        for match in JSX_TEXT_RE.finditer(code):
            text = match.group(1).strip()
            if text and has_words(text):
                yield number, text
        # In copy.ts every string is scanned on its own above; a line there can be a property name.
        if not is_copy_file and PLAIN_TEXT_LINE.match(line) and has_words(line) and not line.startswith(("return", "const", "let", "if", "else", "case", "throw", "await")):
            yield number, line


class PyCopy(ast.NodeVisitor):
    """Collect user-facing string constants, skipping docstrings, logging and raises."""

    def __init__(self, only_kwargs: set[str] | None = None) -> None:
        self.found: list[tuple[int, str]] = []
        self.only_kwargs = only_kwargs

    def _collect(self, node: ast.AST) -> None:
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, str) and has_words(child.value):
                if child.value not in ADMIN_ONLY:
                    self.found.append((child.lineno, child.value))

    def visit_Expr(self, node: ast.Expr) -> None:  # docstrings and bare calls
        if isinstance(node.value, ast.Constant):
            return
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise) -> None:
        # Internal exceptions are not copy, but HTTPException details are.
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and getattr(child.func, "id", "") == "HTTPException":
                for keyword in child.keywords:
                    if keyword.arg == "detail":
                        self._collect(keyword.value)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        name = getattr(func, "attr", getattr(func, "id", ""))
        if name in {"warning", "info", "error", "debug", "exception", "getLogger", "add_middleware"}:
            return
        if self.only_kwargs is not None:
            for keyword in node.keywords:
                if keyword.arg in self.only_kwargs:
                    self._collect(keyword.value)
        elif name == "HTTPException":
            for keyword in node.keywords:
                if keyword.arg == "detail":
                    self._collect(keyword.value)
            return
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value in {"message", "detail"}:
                self._collect(value)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if self.only_kwargs is None and any(isinstance(t, ast.Name) and t.id.isupper() and not t.id.startswith("UNSAFE_") for t in node.targets):
            if isinstance(node.value, (ast.Constant, ast.JoinedStr)) or isinstance(node.value, ast.Tuple):
                self._collect(node.value)
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        if self.only_kwargs is None:
            self._collect(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # String defaults such as `text: str = "..."` are spoken or shown.
        for default in node.args.defaults + [d for d in node.args.kw_defaults if d is not None]:
            self._collect(default)
        for statement in node.body:
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
                continue  # docstring
            self.visit(statement)

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]


def python_copy(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    visitor = PyCopy()
    visitor.visit(tree)
    return visitor.found


def planner_questions(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    visitor = PyCopy(only_kwargs={"initial_question"})
    visitor.visit(tree)
    return visitor.found


def prompt_copy(path: Path):
    active = True
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        marker = line.strip()
        if marker == "<!-- copy-lint: off -->":
            active = False
            continue
        if marker == "<!-- copy-lint: on -->":
            active = True
            continue
        if active and line.strip():
            yield number, line


def main() -> int:
    quiet = "--quiet" in sys.argv
    failures: list[str] = []
    warnings: list[str] = []
    scanned = 0

    def check(path: Path, items) -> None:
        nonlocal scanned
        rel = path.relative_to(ROOT).as_posix()
        scanned += 1
        for line, text in items:
            for hit in find_banned(text):
                failures.append(f"{rel}:{line}: banned word '{hit}' in: {text.strip()[:110]}")
            for hit, hint in find_soft(text):
                warnings.append(f"{rel}:{line}: prefer {hint!r} over '{hit}'")

    for path in sorted(WEB_SRC.rglob("*")):
        if path.suffix in {".ts", ".tsx"} and path.name != "database.types.ts" and "proxy" not in path.name:
            check(path, web_copy(path))
    for name in PY_FILES:
        check(ROOT / "apps/api/app" / name, python_copy(ROOT / "apps/api/app" / name))
    check(ROOT / "apps/api/app/planner_service.py", planner_questions(ROOT / "apps/api/app/planner_service.py"))
    for path in PROMPTS:
        check(path, prompt_copy(path))

    if not quiet:
        for warning in dict.fromkeys(warnings):
            print(f"warn  {warning}")
    for failure in failures:
        print(f"FAIL  {failure}")
    print(f"copy lint: {scanned} files scanned, {len(failures)} banned-word hits, {len(set(warnings))} soft-avoid warnings")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
