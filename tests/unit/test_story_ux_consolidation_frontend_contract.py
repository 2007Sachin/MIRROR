"""My Stories UX consolidation: one state, one action per story; history and archive secondary."""

from pathlib import Path

WEB = Path(__file__).parents[2] / "apps" / "web" / "src"
read = lambda *parts: (WEB.joinpath(*parts)).read_text(encoding="utf-8")  # noqa: E731

STORY_VIEW = read("lib", "story-view.ts")
COPY = read("lib", "copy.ts")
LIST = read("components", "stories", "stories-page.tsx")
EDITOR = read("components", "stories", "story-editor.tsx")
STATE_FN = STORY_VIEW[STORY_VIEW.index("export function storyState"):]
STATE_FN = STATE_FN[:STATE_FN.index("\n}\n") + 3]


def test_story_state_is_one_deterministic_function() -> None:
    # A suggestion always wins; then completeness; then whether it has ever been practised.
    order = ["info.openSuggestionId", 'story.completeness !== "READY"', "!info.hasBeenPracticed"]
    positions = [STATE_FN.index(clause) for clause in order]
    assert positions == sorted(positions)
    assert '"ADD_DETAIL"' in STATE_FN and '"READY"' in STATE_FN and '"PRACTISED"' in STATE_FN and '"SUGGESTED"' in STATE_FN
    # It never invents a quality judgement: only these persisted facts feed the decision.
    assert "Math." not in STATE_FN and "score" not in STATE_FN.lower() and "rating" not in STATE_FN.lower()


def test_the_state_gives_exactly_one_action() -> None:
    for state in ("SUGGESTED", "ADD_DETAIL", "READY", "PRACTISED"):
        assert STATE_FN.count(f'key: "{state}"') == 1
    # Each branch returns exactly one action, never a list of equally weighted choices.
    assert STATE_FN.count("action: { label: t.") == 4


def test_the_library_shows_one_action_per_story() -> None:
    # Section 9 redesign: the card states readiness in plain words and offers one verb per
    # outcome (Add detail, or Practice this story + Edit story), from storyActions.
    assert "storyActions(story, open?.id)" in LIST
    assert "action.href" in LIST and "action.label" in LIST
    assert "L.readiness[story.completeness]" in LIST
    assert "completenessClass(story)" not in LIST and "completenessLabel(story)" not in LIST
    assert "{t.edit}" not in LIST


def test_role_context_only_shows_when_it_exists() -> None:
    assert "story.role_profile_ids.length ? " in LIST
    assert "usefulFor(story, data.roles)" in LIST  # still available, just not shown for every story


def test_open_suggestion_count_is_not_shown_as_a_headline_number() -> None:
    # The count survives (a real, tested capability - see §17/25) but only as a title
    # attribute for more than one open suggestion, not as prose competing with the badge.
    assert 'title={open && open.count > 1 ? t.suggestions.count(open.count) : undefined}' in LIST


def test_story_fields_are_grouped_not_a_flat_wall_of_nine_fields() -> None:
    assert "STORY_PART_GROUPS" in STORY_VIEW
    groups = STORY_VIEW[STORY_VIEW.index("export const STORY_PART_GROUPS"):STORY_VIEW.index("];", STORY_VIEW.index("export const STORY_PART_GROUPS"))]
    for part in ("situation", "ownership", "actions", "reasoning", "trade_offs", "outcome", "measurable_result", "learning", "do_differently"):
        assert f'"{part}"' in groups
    assert groups.count('{ key: "') == 4  # four groups, not nine flat fields
    assert "STORY_PART_GROUPS.map" in EDITOR and "<fieldset" in EDITOR and "<legend>" in EDITOR
    # The suggestion focus/scroll target and read-only behaviour still work per field.
    assert 'id={`story-part-${part}`}' in EDITOR and '"is-suggested"' in EDITOR


def test_history_is_collapsed_by_default_and_archive_is_last() -> None:
    assert "<details" in EDITOR and "dh-story-history-disclosure" in EDITOR
    disclosure = EDITOR[EDITOR.index("<details"):EDITOR.index("</details>")]
    assert "<StoryHistory" in disclosure
    # Archive sits after the disclosure in the page, and only for an active story.
    assert EDITOR.index("</details>") < EDITOR.index("dh-story-manage")
    assert "archived ? null : (" in EDITOR[EDITOR.index("</details>"):]


def test_suggestions_roles_and_practice_come_before_history() -> None:
    order = ["<StorySuggestions", "<StoryRoles", "<StoryPractice", "<details"]
    positions = [EDITOR.index(needle) for needle in order]
    assert positions == sorted(positions)


def test_new_copy_stays_candidate_facing() -> None:
    for phrase in ("Add detail", "Ready to practise", "Practised", "Improvement suggested", "Continue story", "Practise again", "See earlier versions"):
        assert phrase in COPY
    for internal in ("state machine", "selector", "derive", "priority order"):
        assert internal not in COPY.lower()
