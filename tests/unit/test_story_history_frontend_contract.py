"""My Stories history and archive: the UI renders backend state and never rewrites history."""

import re
from pathlib import Path

WEB = Path(__file__).parents[2] / "apps" / "web" / "src"
read = lambda *parts: (WEB.joinpath(*parts)).read_text(encoding="utf-8")  # noqa: E731

API = read("lib", "api.ts")
COPY = read("lib", "copy.ts")
STORY_VIEW = read("lib", "story-view.ts")
EDITOR = read("components", "stories", "story-editor.tsx")
HISTORY = read("components", "stories", "story-history.tsx")
LIST = read("components", "stories", "stories-page.tsx")
STORY_COPY = COPY[COPY.index("export const stories = {"):COPY.index("export const tryAgain")]


def test_the_client_archives_instead_of_deleting() -> None:
    assert "/api/v1/stories/${id}/archive" in API
    assert '`/api/v1/stories/${id}`, { method: "DELETE" }' not in API  # a story itself is never deleted
    assert "deleteStory" not in API + EDITOR + LIST
    assert "/api/v1/stories?archived=true" in API


def test_restoring_a_version_goes_through_the_backend() -> None:
    assert "/api/v1/stories/${id}/versions/${versionId}/restore" in API
    assert "mirrorApi.restoreStoryVersion" in HISTORY
    # Earlier versions are never sent back as an edit.
    assert "updateStory" not in HISTORY


def test_the_editor_offers_history_and_a_reversible_archive() -> None:
    assert "<StoryHistory" in EDITOR
    assert "mirrorApi.archiveStory" in EDITOR and "mirrorApi.restoreStory" in EDITOR
    assert "ArchiveDialog" in EDITOR and "showModal" in EDITOR
    assert "Trash" not in EDITOR and "is-danger" not in EDITOR  # archiving is not destructive


def test_an_archived_story_is_read_only_in_the_editor() -> None:
    assert "readOnly={archived}" in EDITOR
    assert "readOnly ? null" in EDITOR  # no save button while archived
    assert "t.archived.notice" in EDITOR


def test_history_shows_current_and_earlier_versions_read_only() -> None:
    assert ".storyVersions(story.id)" in HISTORY
    assert "t.history.current" in HISTORY and "t.history.earlier" in HISTORY
    assert "version.version === story.current_version" in HISTORY  # "current" comes from the backend
    earlier = HISTORY[HISTORY.index("function EarlierVersion"):]
    assert "<dl>" in earlier and "<textarea" not in earlier and "<input" not in earlier
    assert "t.history.readOnly" in earlier


def test_history_has_loading_error_and_blocked_states() -> None:
    assert "<PageLoading" in HISTORY and "t.errors.history" in HISTORY and "onRetry" in HISTORY
    assert "t.history.saveFirst" in HISTORY and "t.history.archivedFirst" in HISTORY
    assert "unsavedChanges" in EDITOR


def test_my_stories_lists_archived_stories_separately_with_restore() -> None:
    assert "mirrorApi.stories({ archived: true })" in LIST
    assert "data.active.map" in LIST and "data.archived.map" in LIST
    assert "mirrorApi.restoreStory" in LIST
    assert "t.archived.title" in LIST


def test_story_copy_uses_plain_words() -> None:
    for phrase in ("Version history", "Current version", "Earlier version", "Archive story", "You can restore it later."):
        assert phrase in STORY_COPY
    for internal in ("snapshot", "revision", "audit", "pointer", "immutable", "Delete story", "can't be recovered"):
        assert internal.lower() not in STORY_COPY.lower()
    assert "Restored from version" in STORY_COPY and "Updated ${day}" in STORY_COPY
    assert re.search(r"RESTORED\(day, version\.restored_from_version\)", STORY_VIEW)
