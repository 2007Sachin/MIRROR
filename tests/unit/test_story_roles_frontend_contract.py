"""My Stories roles: one story reused across exact roles, framed without copying it."""

from pathlib import Path

WEB = Path(__file__).parents[2] / "apps" / "web" / "src"
read = lambda *parts: (WEB.joinpath(*parts)).read_text(encoding="utf-8")  # noqa: E731

API = read("lib", "api.ts")
COPY = read("lib", "copy.ts")
STORY_VIEW = read("lib", "story-view.ts")
EDITOR = read("components", "stories", "story-editor.tsx")
ROLES = read("components", "stories", "story-roles.tsx")
LIST = read("components", "stories", "stories-page.tsx")
ROLE_COPY = COPY[COPY.index("  roles: {", COPY.index("export const stories = {")):COPY.index("  practice: {", COPY.index("export const stories = {"))]


def test_the_client_frames_roles_by_exact_id() -> None:
    assert "/api/v1/stories/${id}/roles/${roleProfileId}" in API
    assert 'method: "PUT"' in API[API.index("setStoryRole"):API.index("removeStoryRole")]
    assert 'method: "DELETE"' in API[API.index("removeStoryRole"):API.index("retryTurnAudio")]
    assert "role_profile_ids: string[]" in API


def test_a_framing_carries_no_story_content() -> None:
    framing = API[API.index("export type StoryRoleFramingInput"):]
    framing = framing[:framing.index("};")]
    assert "themes" in framing and "emphasis" in framing
    for part in ("situation", "actions", "outcome", "measurable_result", "title"):
        assert part not in framing
    # Editing a story's content cannot change which role it was written for.
    assert '"role_profile_id"' in API[API.index("export type StoryContentInput"):API.index("export type PressureQuestionKind")]


def test_the_story_page_shows_adds_and_removes_roles() -> None:
    assert "<StoryRoles story={data} />" in EDITOR
    assert "mirrorApi.storyRoles" in ROLES and "mirrorApi.roles()" in ROLES
    assert "mirrorApi.setStoryRole" in ROLES and "mirrorApi.removeStoryRole" in ROLES
    assert "createStory" not in ROLES  # adding a role never makes a second story
    assert "!framed.has(role.id)" in ROLES  # only roles not already linked can be added


def test_roles_are_told_apart_by_id_not_by_name() -> None:
    assert "item.id === roleProfileId" in STORY_VIEW
    assert "sameName.length > 1" in STORY_VIEW  # same-named roles get a date to tell them apart
    assert "target_role ===" not in ROLES and "target_role ===" not in LIST


def test_archived_stories_keep_their_roles_read_only() -> None:
    assert "const archived = Boolean(story.archived_at)" in ROLES
    assert "{archived ? null : (" in ROLES and "t.archived" in ROLES


def test_role_section_has_loading_error_and_empty_states() -> None:
    assert "<PageLoading" in ROLES and "copy.errors.roles" in ROLES and "onRetry" in ROLES
    assert "t.none" in ROLES and "t.allLinked" in ROLES and "t.noRoles" in ROLES


def test_the_library_says_where_each_story_is_useful() -> None:
    assert "usefulFor(story, data.roles)" in LIST
    assert "mirrorApi.roles().catch" in LIST  # role names never block the list
    assert "t.roles.acrossRoles" in STORY_VIEW


def test_starting_a_story_for_a_role_suggests_reusing_one() -> None:
    new_story = EDITOR[EDITOR.index("export function NewStory"):]
    assert "t.roles.reuse" in new_story and 'href="/stories"' in new_story


def test_role_copy_is_plain() -> None:
    for phrase in ("Useful for", "Useful across roles", "Add a role", "Emphasize for this role"):
        assert phrase in ROLE_COPY
    for internal in ("mapping", "join", "association", "framing", "record"):
        assert internal not in ROLE_COPY.lower()
