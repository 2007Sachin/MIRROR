"""Guided stories (blueprint section 9): one question at a time, save for later, approved items only."""

import re
from pathlib import Path

WEB = Path(__file__).parents[2] / "apps" / "web" / "src"
read = lambda *parts: (WEB.joinpath(*parts)).read_text(encoding="utf-8")  # noqa: E731

EDITOR = read("components", "stories", "story-editor.tsx")
LIST = read("components", "stories", "stories-page.tsx")
DRILL = read("components", "roles", "pressure-test-page.tsx")
API = read("lib", "api-stories-guided.ts")
COPY = read("lib", "copy-stories.ts")
CSS = read("styles", "stories-guided.css")
NEW_STORY = EDITOR[EDITOR.index("export function NewStory"):EDITOR.index("function StoryForm(")]
ACTIONS = LIST[LIST.index("export function storyActions"):LIST.index("export function StoriesPage")]


def test_guided_steps_are_shown_one_at_a_time_with_progress() -> None:
    steps = COPY[COPY.index("  steps: ["):COPY.index("satisfies readonly GuidedStep[]")]
    names = re.findall(r'name: "(\w+)"', steps)
    assert names == ["Context", "Challenge", "Action", "Result", "Learning"]
    # The steps map onto existing story fields only; the database is unchanged.
    for part in ("situation", "ownership", "actions", "reasoning", "outcome", "measurable_result", "learning"):
        assert f'part: "{part}"' in steps
    assert "steps[step]" in NEW_STORY and "current.question(theme)" in NEW_STORY
    assert "g.progress(step + 1, steps.length)" in NEW_STORY
    assert "`${step} of ${total}`" in COPY
    # Only the current question's field is rendered, never the whole list of parts.
    assert "STORY_PART_GROUPS" not in NEW_STORY and "<StoryForm" not in NEW_STORY


def test_save_for_later_is_on_every_step_and_confirms() -> None:
    assert 'saveForLater: "Save for later"' in COPY
    assert 'saved: "Saved. You can return to this whenever you are ready."' in COPY
    # The Save for later button sits outside the last-step branch, so every step has it.
    actions = NEW_STORY[NEW_STORY.index('<div className="dh-action-row">', NEW_STORY.index("sg-steps")):]
    branch_end = actions.index(")}", actions.index("{last ? ("))
    assert "g.saveForLater" in actions[branch_end:]
    assert "persist(false)" in actions and "setNotice(g.saved)" in NEW_STORY
    # A second save updates the same story instead of creating a duplicate.
    assert "saved\n        ? await mirrorApi.updateStory(saved.id" in NEW_STORY


def test_a_failed_save_keeps_the_writing_and_offers_retry() -> None:
    catch = NEW_STORY[NEW_STORY.index("} catch (reason) {"):NEW_STORY.index("} finally {")]
    assert "setDraft" not in catch
    assert "onRetry={() => void persist(retryFinish)}" in NEW_STORY


def test_evidence_prefill_uses_only_approved_items() -> None:
    assert 'item.id === id && item.status === "APPROVED"' in API
    assert 'from "@/lib/api"' in API and "request<" in API
    assert 'params.get("evidence")' in NEW_STORY and "approvedEvidenceItem(evidenceId)" in NEW_STORY
    assert "g.why.notApproved" in NEW_STORY  # anything not approved starts blank
    assert 'params.get("theme")' in NEW_STORY and 'params.get("role")' in NEW_STORY
    assert "g.why.roleTheme(role.target_role, theme)" in NEW_STORY


def test_library_cards_show_purpose_version_readiness_and_last_practice() -> None:
    for word in ('READY: "Ready to tell"', 'DEVELOPING: "Needs more detail"', 'STARTED: "Just started"'):
        assert word in COPY
    assert "L.readiness[story.completeness]" in LIST
    assert "L.purpose(story.themes.join" in LIST and "usefulFor(story, data.roles)" in LIST
    assert "L.version(story.current_version)" in LIST
    assert "practiceLine(data.practice?.get(story.id))" in LIST


def test_archive_copy() -> None:
    assert 'archivedBody: "Your archived stories live here."' in COPY
    assert "body={L.archivedBody}" in LIST


def test_one_verb_per_outcome_and_no_duplicate_actions() -> None:
    assert 'edit: "Edit story"' in COPY and 'addDetail: "Add detail"' in COPY and 'practice: "Practice this story"' in COPY
    # Each branch offers distinct destinations: never "Edit story" and "Add detail" together.
    for branch in ACTIONS.split("return ")[1:]:
        assert not ("L.actions.edit" in branch and "L.actions.addDetail" in branch)
    # One way to add a story, not two links that do the same thing.
    assert LIST.count('href="/stories/new"') == 1 and "findOne" not in LIST and "guided=1" not in LIST
    assert "storyActions(story, open?.id).map" in LIST


def test_a_missing_story_is_a_permanent_not_found() -> None:
    assert 'notFound: "This story cannot be found."' in COPY
    assert "reason.status === 404" in EDITOR
    block = EDITOR[EDITOR.index("state === \"ready\" && !data"):]
    block = block[:block.index(") : null}")]
    assert "storyLibrary.notFound" in block and 'href="/stories"' in block
    assert "onRetry" not in block and "reload" not in block


def test_dig_deeper_feedback_is_structured_and_keeps_the_answer() -> None:
    assert "feedback.clear" in DRILL and "feedback.missing" in DRILL and "feedback.next_sentence" in DRILL
    assert "answerFeedback(question.kind, draft.trim())" in DRILL
    for name in ("check", "save"):
        fn = DRILL[DRILL.index(f"async function {name}()"):]
        catch = fn[fn.index("} catch"):fn.index("\n  }\n")]
        assert "setDraft" not in catch and "setRetry(" in catch
    assert "f.retry" in DRILL and 'role="alert"' in DRILL


def test_no_blue_and_tokens_only() -> None:
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", CSS)
    for source in (CSS, EDITOR, LIST, DRILL, COPY, API):
        assert not re.search(r"\b(blue|cobalt|indigo|teal|navy|sky)\b", source, re.IGNORECASE)
