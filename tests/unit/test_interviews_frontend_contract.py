"""Interview tomorrow + Debrief: the UI renders backend decisions and keeps its copy honest."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).parents[2] / "apps" / "web" / "src"
read = lambda *parts: (WEB.joinpath(*parts)).read_text(encoding="utf-8")  # noqa: E731

API = read("lib", "api.ts")
COPY = read("lib", "copy.ts")
VIEW = read("lib", "interview-view.ts")
TABS = read("components", "roles", "role-tabs.tsx")
LIST = read("components", "interviews", "interviews-page.tsx")
BRIEF = read("components", "interviews", "interview-brief-page.tsx")
FORM = read("components", "interviews", "interview-form.tsx")


def interviews_copy() -> str:
    return COPY[COPY.index("export const interviews = {") :]


def test_all_seven_endpoints_are_typed_in_the_api_client() -> None:
    for path in (
        "/api/v1/roles/${roleProfileId}/interviews`)",
        '/api/v1/roles/${roleProfileId}/interviews`, { method: "POST"',
        '/api/v1/interviews/${eventId}`, { method: "PATCH"',
        '/api/v1/interviews/${eventId}`, { method: "DELETE"',
        "/api/v1/interviews/${eventId}/brief`",
        "/api/v1/interviews/${eventId}/debrief`)",
        '/api/v1/interviews/${eventId}/debrief`, { method: "PUT"',
    ):
        assert path in API, path
    # No debrief yet is a normal state, not an error.
    assert "reason.status === 404) return null" in API


def test_the_role_workspace_has_an_interviews_tab() -> None:
    assert "/roles/${roleProfileId}/interviews" in TABS
    assert 'interviews: "Interviews"' in COPY
    assert (WEB / "app" / "roles" / "[role_profile_id]" / "interviews" / "page.tsx").exists()
    assert (WEB / "app" / "roles" / "[role_profile_id]" / "interviews" / "[event_id]" / "page.tsx").exists()


def test_timing_and_brief_come_from_the_backend() -> None:
    # The UI never works out "soon" or "past" from the clock itself.
    assert "Date.now" not in VIEW and "new Date()" not in VIEW
    assert 'event.timing === "PAST"' in VIEW
    assert "mirrorApi.interviewBrief" in BRIEF and "mirrorApi.interviewDebrief" in BRIEF


def test_the_add_form_sends_a_timezone_aware_time() -> None:
    assert 'type="datetime-local"' in FORM and "<InterviewForm" in LIST
    assert "localInputToIso(when)" in FORM and "getTimezoneOffset" in VIEW
    assert "maxLength={MAX_COMPANY_LENGTH}" in FORM and "MAX_COMPANY_LENGTH = 120" in VIEW


def test_the_brief_reuses_map_wording_and_always_shows_limitations() -> None:
    assert "coverageLabel(theme.coverage)" in BRIEF
    assert "pressureTestHref(roleProfileId)" in BRIEF
    assert "brief.limitations.map" in BRIEF
    limits = BRIEF[BRIEF.index('id="brief-limits"') - 200 : BRIEF.index('id="brief-limits"')]
    assert "? (" not in limits  # not behind a condition


def test_debrief_form_and_save_status() -> None:
    assert "normaliseQuestions(questions)" in BRIEF
    assert 'aria-live="polite"' in BRIEF
    assert BRIEF.count('className="dh-primary-action"') == 1
    assert "dh-primary-action" not in LIST
    # Add is the list's one primary; edit on the brief stays quiet next to the debrief's save.
    assert 'event ? "dh-text-action" : "dh-primary-action"' in FORM


def test_edit_details_reuses_the_form_and_trusts_the_server() -> None:
    # One shared form for add and edit, prefilled from the stored event.
    assert "<InterviewForm" in BRIEF and "event={event}" in BRIEF
    assert "isoToLocalInput(event.scheduled_for)" in FORM
    # Clearing the company label sends null; a second submit is ignored while one is in flight.
    assert "company_label: company.trim() || null" in FORM
    assert "if (busy) return" in FORM and "disabled={busy || !when}" in FORM
    assert 'role="alert"' in FORM and 'aria-live="polite"' in BRIEF
    # The shown event (and its timing) is replaced by the PATCH response, and focus goes back to the toggle.
    assert "onSaved(await mirrorApi.updateInterview(event.id, value))" in BRIEF
    assert "openRef.current?.focus()" in BRIEF
    # The edit toggle is a text action, never a second filled primary.
    assert 'className="dh-text-action" onClick' in BRIEF
    assert 'open: "Edit details"' in interviews_copy()


def test_interview_copy_uses_the_agreed_wording_and_no_predictions() -> None:
    text = interviews_copy()
    for phrase in ("Questions worth preparing for", "Questions you could ask them", "How it went"):
        assert phrase in text
    for bad in (r"you will be asked", r"\d+\s*%", r"\bbecause\b", r"\bwhy you\b", r"\bpredict", r"\bchance"):
        assert not re.search(bad, text, re.IGNORECASE), bad


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_normalise_questions_behaviour(tmp_path: Path) -> None:
    body = VIEW[VIEW.index("export function normaliseQuestions") :]
    script = tmp_path / "check.mjs"
    script.write_text(
        "const MAX_QUESTIONS = 15; const MAX_QUESTION_LENGTH = 500;\n"
        + re.sub(r"\(text: string\): string\[\]", "(text)", body)
        .replace("export ", "")
        .replace("new Set<string>()", "new Set()")
        .replace("const out: string[] = []", "const out = []")
        + "\nconst r = normaliseQuestions(' A \\n\\na\\nB\\r\\n' + Array.from({length: 20}, (_, i) => 'q' + i).join('\\n'));"
        + "\nif (JSON.stringify(r.slice(0, 2)) !== '[\"A\",\"B\"]' || r.length !== 15) { console.error(r); process.exit(1); }\n",
        encoding="utf-8",
    )
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize("tz", ["UTC", "Asia/Kolkata", "America/New_York"])
def test_iso_and_local_input_round_trip(tmp_path: Path, tz: str) -> None:
    def fn(name: str) -> str:
        body = VIEW[VIEW.index(f"export function {name}") :]
        body = body[: body.index("\n}\n") + 3]
        return re.sub(r"\((\w+): string\)(: string \| null|: string)?", r"(\1)", body).replace("export ", "").replace("(n: number)", "(n)")

    script = tmp_path / "round.mjs"
    script.write_text(
        fn("localInputToIso") + fn("isoToLocalInput") + """
const fail = (m) => { console.error(m); process.exit(1); };
for (const value of ["2026-10-01T09:30", "2026-03-29T23:05", "2026-12-31T00:00"]) {
  const iso = localInputToIso(value);
  if (!iso || isoToLocalInput(iso) !== value) fail([value, iso, iso && isoToLocalInput(iso)]);
}
// A stored UTC instant becomes the browser's wall time, and back to the same instant.
const stored = "2026-10-01T04:00:00+00:00";
const local = isoToLocalInput(stored);
const expected = { "UTC": "2026-10-01T04:00", "Asia/Kolkata": "2026-10-01T09:30", "America/New_York": "2026-10-01T00:00" }[process.env.TZ];
if (local !== expected) fail(["prefill", local, expected]);
if (new Date(localInputToIso(local)).getTime() !== new Date(stored).getTime()) fail(["instant", localInputToIso(local)]);
if (isoToLocalInput("nope") !== "") fail("invalid");
""",
        encoding="utf-8",
    )
    result = subprocess.run(["node", str(script)], capture_output=True, text=True, env={**os.environ, "TZ": tz})
    assert result.returncode == 0, result.stderr
