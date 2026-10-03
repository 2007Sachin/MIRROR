"""Review -> story suggestions in the UI: guidance, never a rewrite; the candidate edits and saves."""

from pathlib import Path

WEB = Path(__file__).parents[2] / "apps" / "web" / "src"
read = lambda *parts: (WEB.joinpath(*parts)).read_text(encoding="utf-8")  # noqa: E731

API = read("lib", "api.ts")
COPY = read("lib", "copy.ts")
STORY_VIEW = read("lib", "story-view.ts")
SUGGESTIONS = read("components", "stories", "story-suggestions.tsx")
EDITOR = read("components", "stories", "story-editor.tsx")
LIST = read("components", "stories", "stories-page.tsx")
REVIEW = read("components", "review", "review-page.tsx")
SECTION = COPY[COPY.index("  suggestions: {"):COPY.index("  history: {", COPY.index("  suggestions: {"))]


def test_review_shows_suggestions_only_when_there_are_open_ones() -> None:
    assert "<ReviewStorySuggestions sessionId={sessionId} />" in REVIEW
    review_part = SUGGESTIONS[SUGGESTIONS.index("export function ReviewStorySuggestions"):]
    assert "mirrorApi.sessionStorySuggestions(sessionId)" in review_part
    assert "if (!open.length) return null;" in review_part
    assert ".catch(() => undefined)" in review_part  # a review never breaks because of suggestions


def test_review_never_changes_a_story() -> None:
    for mutation in ("updateStory", "restoreStoryVersion", "archiveStory", "acceptStorySuggestion"):
        assert mutation not in SUGGESTIONS
        assert mutation not in REVIEW


def test_improve_opens_the_editor_and_dismiss_keeps_the_story() -> None:
    assert "improveHref(suggestion)" in SUGGESTIONS and "?${new URLSearchParams({ suggestion: suggestion.id })" in STORY_VIEW
    assert "mirrorApi.dismissStorySuggestion(suggestion.id)" in SUGGESTIONS
    assert "suggestion.story_archived ? null" in SUGGESTIONS  # no Improve on an archived story


def test_the_editor_shows_context_focuses_the_part_and_accepts_only_after_a_new_version() -> None:
    assert 'useSearchParams().get("suggestion")' in EDITOR
    assert "document.getElementById(`story-part-${suggestion.story_part}`)" in EDITOR
    assert 'id={`story-part-${part}`}' in EDITOR and '"is-suggested"' in EDITOR
    save = EDITOR[EDITOR.index("async function save"):EDITOR.index("async function archive")]
    assert "saved.current_version > before" in save  # no new version, nothing to accept
    assert "acceptStorySuggestion(suggestion.id, saved.current_version)" in save
    assert "t.suggestions.stillOpen" in save
    assert "t.suggestions.bannerNote" in EDITOR  # the candidate controls the edit


def test_an_older_practised_version_is_called_out() -> None:
    assert "suggestionIsOlder(suggestion)" in EDITOR and "suggestionIsOlder(suggestion)" in SUGGESTIONS
    assert "suggestion.current_version > suggestion.practised_version" in STORY_VIEW


def test_story_page_lists_open_and_earlier_suggestions() -> None:
    assert "<StorySuggestions story={data} />" in EDITOR
    story_part = SUGGESTIONS[SUGGESTIONS.index("export function StorySuggestions"):SUGGESTIONS.index("export function ReviewStorySuggestions")]
    assert 'item.status === "OPEN"' in story_part and "<details" in story_part
    assert "t.accepted(item.resolved_version)" in story_part and "t.dismissed" in story_part
    assert "<PageLoading" in story_part and "copy.errors.suggestions" in story_part
    assert "roleLabel(suggestion.role_profile_id, roles)" in SUGGESTIONS  # exact role id


def test_the_library_only_counts_open_suggestions() -> None:
    assert "mirrorApi.openStorySuggestions().catch(() => [])" in LIST
    assert "t.suggestions.count(" in LIST


def test_copy_guides_without_rewriting_or_grading() -> None:
    assert "suggestionCopy(" in SUGGESTIONS and "t.suggestions.issue[suggestion.issue_type]" in STORY_VIEW
    for phrase in ("Improve this story", "Improve story", "Dismiss", "the one you practised"):
        assert phrase in SECTION
    for bad in ("score", "weak", "strong", "rating", "rewrite", "rewritten", "evaluat", "skeptic"):
        assert bad not in SECTION.lower()
