"""My Stories practice history: shows only persisted usage, by exact role and version, never a score."""

from pathlib import Path

WEB = Path(__file__).parents[2] / "apps" / "web" / "src"
read = lambda *parts: (WEB.joinpath(*parts)).read_text(encoding="utf-8")  # noqa: E731

API = read("lib", "api.ts")
COPY = read("lib", "copy.ts")
STORY_VIEW = read("lib", "story-view.ts")
START_LIB = read("lib", "start-practice.ts")
EDITOR = read("components", "stories", "story-editor.tsx")
PRACTICE = read("components", "stories", "story-practice.tsx")
LIST = read("components", "stories", "stories-page.tsx")
START = read("components", "practice", "start-practice.tsx")
STORY_COPY = COPY[COPY.index("export const stories = {"):COPY.index("export const tryAgain")]


def test_the_client_reads_usage_the_server_recorded() -> None:
    assert "/api/v1/stories/${id}/practice" in API and '"/api/v1/story-practice"' in API
    assert "story_version: number" in API and "role_profile_id: string | null" in API
    assert "...(story_ids?.length ? { story_ids } : {})" in API  # only an explicit choice is sent


def test_a_story_is_only_used_when_the_candidate_chooses_it() -> None:
    assert "storyIds?: string[]" in START_LIB and "idempotencyKey, storyIds)" in START_LIB
    assert 'params.get("story")' in START
    assert "[data.story.id]" in START  # exactly the story on the page, nothing inferred
    # A story practice never falls through to setup, which would silently drop the story.
    story_branch = START[START.index("if (storyId) {"):START.index("if (direct) {")]
    assert "setupHref" not in story_branch and "t.story.roleNeeded" in story_branch
    assert 'mode !== "FULL_INTERVIEW"' in START  # stories are practised in short practices only


def test_the_story_page_shows_its_practice_history() -> None:
    assert "<StoryPractice story={data} />" in EDITOR
    assert "mirrorApi.storyPractice(story.id)" in PRACTICE
    assert "roleLabel(record.role_profile_id, load.roles)" in PRACTICE  # exact role id, not a name
    assert "t.version(record.story_version)" in PRACTICE
    assert "state.reviewHref" in PRACTICE and "reviewHref(record.session_id)" in STORY_VIEW


def test_history_has_loading_error_and_empty_states() -> None:
    assert "<PageLoading" in PRACTICE and "copy.errors.practice" in PRACTICE and "onRetry" in PRACTICE
    assert "t.none" in PRACTICE


def test_archived_stories_keep_their_history_but_cannot_start_a_new_practice() -> None:
    assert "const action = archived ? null" in PRACTICE
    assert "t.archivedNote" in PRACTICE
    assert "story && !story.archived_at ? story : null" in START
    assert "data.archived.map" in LIST and "practiceLine(data.practice.get(story.id))" in LIST


def test_the_library_shows_counts_without_judging_stories() -> None:
    assert "mirrorApi.storyPracticeSummaries().catch" in LIST  # counts never block the list
    assert "practiceLine(" in LIST and "summary?.practice_count" in STORY_VIEW
    for judgement in ("strong", "weak", "score", "grade", "rating", "best story"):
        assert judgement not in STORY_COPY[STORY_COPY.index("  practice: {"):STORY_COPY.index("  suggestions: {")].lower()


def test_practice_copy_is_plain() -> None:
    section = STORY_COPY[STORY_COPY.index("  practice: {"):STORY_COPY.index("  suggestions: {")]
    for phrase in ("Practice history", "Practise this story", "Not practised yet", "Open review"):
        assert phrase in section
    for internal in ("usage", "record", "session", "version id"):
        assert internal not in section.lower()
