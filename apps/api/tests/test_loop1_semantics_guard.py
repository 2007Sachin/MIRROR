"""Loop 1 semantics stay untouched by Loop 2 targets (import graph + behaviour).

(a) No Loop 1 assessment/report/progress/planning module can reach a Loop 2 module through
    imports (module-level or inside functions). The only bridge is the planner's injected
    prompt loader, wired in ``dependencies``.
(b) Behaviour: role-level progress still counts target-linked sessions like any other practice
    of the role, and plans without stored prompts are unchanged (test_target_seams.py); the
    report/assessment path cannot see targets at all, by (a).
"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
LOOP2 = {
    "target_rounds", "target_repository", "target_capability", "target_service", "routes_targets", "research_catalog",
    "prompt_originality", "target_priority", "target_taxonomy",  # target_taxonomy: Loop 3 role-family data loader
}
GUARDED_PREFIXES = ("assessment_", "verdict_", "skeptic_", "specialist_", "report_", "claim_resolution_")
GUARDED = {
    "final_assessment_aggregator", "state_machine", "interview_engine", "evidence_validator", "role_progress",
    "progress_summary", "plan_service", "routes_plan", "planner_service", "planner_models", "practice_modes",
    "interviewer_service", "interviewer_context", "dashboard_service", "home_service", "routes_sessions_lifecycle",
}


def _module_name(path: Path) -> str:
    return ".".join(path.relative_to(APP).with_suffix("").parts)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    package = _module_name(path).split(".")[:-1]
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app."):
                    found.add(alias.name[4:])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - node.level + 1] if node.level > 1 else package
                stem = ".".join([*base, node.module] if node.module else base)
            elif node.module and node.module.startswith("app."):
                stem = node.module[4:]
            elif node.module == "app":
                stem = ""
            else:
                continue
            found.add(stem)
            for alias in node.names:
                found.add(f"{stem}.{alias.name}" if stem else alias.name)
    return {name for name in found if name}


def _graph() -> dict[str, set[str]]:
    modules = {_module_name(path): path for path in APP.rglob("*.py")}
    graph = {}
    for name, path in modules.items():
        graph[name] = {dep for dep in _imports(path) if dep in modules}
    return graph


# Composition roots wire services together and are not part of any Loop 1 behaviour; the
# Loop 2 imports inside them are pinned separately below.
COMPOSITION_ROOTS = {"dependencies", "main"}


def _reach(graph: dict[str, set[str]], start: str) -> set[str]:
    seen, stack = set(), [start]
    while stack:
        node = stack.pop()
        for dep in graph.get(node, ()):
            if dep in COMPOSITION_ROOTS:
                continue
            if dep not in seen:
                seen.add(dep)
                stack.append(dep)
    return seen


def _guarded(graph: dict[str, set[str]]) -> list[str]:
    return sorted(
        name for name in graph
        if "." not in name and (name in GUARDED or name.startswith(GUARDED_PREFIXES))
    )


def test_guarded_set_is_not_empty_and_includes_the_report_path() -> None:
    guarded = _guarded(_graph())
    for name in ("report_service", "final_assessment_aggregator", "role_progress", "planner_service", "practice_modes", "assessment_orchestrator"):
        assert name in guarded


def test_no_loop1_module_reaches_a_loop2_module() -> None:
    graph = _graph()
    offenders = {name: sorted(_reach(graph, name) & LOOP2) for name in _guarded(graph)}
    assert {name: hit for name, hit in offenders.items() if hit} == {}


def test_the_only_bridge_is_the_injected_planner_loader_in_dependencies() -> None:
    graph = _graph()
    importers = sorted(name for name, deps in graph.items() if deps & LOOP2 and name not in LOOP2)
    assert importers == ["dependencies", "main"]


def test_dependencies_reaches_loop2_only_inside_the_planner_loader() -> None:
    tree = ast.parse((APP / "dependencies.py").read_text(encoding="utf-8"))
    for node in tree.body:  # module level: no Loop 2 import at all
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[-1] not in LOOP2
    holders = sorted(
        fn.name for fn in ast.walk(tree) if isinstance(fn, ast.AsyncFunctionDef | ast.FunctionDef)
        for inner in ast.walk(fn) if isinstance(inner, ast.ImportFrom) and (inner.module or "") in LOOP2
    )
    assert holders == ["_target_prompt_texts", "_target_prompt_texts"]


def test_graph_check_is_red_capable() -> None:
    """The walker sees function-level imports (the planner bridge lives inside a function)."""
    assert "routes_targets" in _imports(APP / "dependencies.py")
    assert "target_service" in _imports(APP / "dependencies.py")
