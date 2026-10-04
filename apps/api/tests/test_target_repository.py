"""Target storage: owner scoping, immutability, write-once links, probe and capability states."""

import asyncio
import json
from uuid import uuid4

import httpx
import pytest

from app.config import Settings
from app.target_capability import TargetAvailability, TargetCapability
from app.target_repository import (
    BlueprintPin,
    LinkAlreadyExists,
    MemoryTargetRepository,
    QuestionCreate,
    SupabaseTargetRepository,
    TargetConflict,
    TargetsUnavailable,
    TargetValues,
    TargetSessionLinkCreate,
)

USER_A, USER_B = uuid4(), uuid4()
ROLE = uuid4()


def run(coro):
    return asyncio.run(coro)


def values(**over):
    base = dict(
        role_profile_id=ROLE, company_label="Amazon", company_key="amazon",
        role_family_key="software_development_engineering", level_key="not_sure", level_label=None,
        geography_key="in", geography_label="India", interview_date=None,
    )
    base.update(over)
    return TargetValues(**base)


def question(target_id, set_id, position=1, text="Tell me about a time you made something simpler for others."):
    from app.prompt_originality import novelty_sha256

    return QuestionCreate(
        candidate_target_id=target_id, blueprint_id=None, prompt_set_id=set_id, position=position,
        round_key="behavioural", competency_key="behavioural_examples", family_key="simplifying",
        template_id="behavioural.simplified", generator_version="round-pack-1",
        originality_rules_version="originality-1", question_text=text, rationale_code="MIRROR_SUGGESTED",
        derived_from={"round_key": "behavioural", "story_titles": []}, novelty_sha256=novelty_sha256(text),
    )


# ------------------------------------------------------------------ memory repository


def test_targets_are_owner_scoped() -> None:
    repo = MemoryTargetRepository()
    target = run(repo.create_target(USER_A, values()))
    assert target.level_key == "not_sure" and target.status == "ACTIVE"
    assert run(repo.get_target(target.id, USER_B)) is None
    assert run(repo.list_targets(USER_B)) == []
    assert run(repo.archive_target(target.id, USER_B)) is None
    assert run(repo.get_target(target.id, USER_A)).status == "ACTIVE"


def test_one_active_target_per_scope_and_archive_frees_it() -> None:
    repo = MemoryTargetRepository()
    first = run(repo.create_target(USER_A, values()))
    with pytest.raises(TargetConflict) as raised:
        run(repo.create_target(USER_A, values()))
    assert raised.value.existing_id == first.id
    archived = run(repo.archive_target(first.id, USER_A))
    assert archived.status == "ARCHIVED" and archived.archived_at is not None
    assert archived.company_key == first.company_key and archived.level_key == first.level_key
    run(repo.create_target(USER_A, values()))


def test_blueprints_are_appended_versions_never_rewritten() -> None:
    repo = MemoryTargetRepository()
    target = run(repo.create_target(USER_A, values()))
    pin = BlueprintPin(catalog_version=1, catalog_sha256="a" * 64, match_state="NOT_RESEARCHED", rules_version="r")
    one = run(repo.create_blueprint(USER_A, target.id, pin))
    two = run(repo.create_blueprint(USER_A, target.id, pin.model_copy(update={"catalog_version": 2})))
    assert (one.version, two.version) == (1, 2)
    assert [b.catalog_version for b in run(repo.blueprints(target.id, USER_A))] == [1, 2]
    assert run(repo.blueprints(target.id, USER_B)) == []
    with pytest.raises(LookupError):
        run(repo.create_blueprint(USER_B, target.id, pin))


def test_questions_are_unique_per_session_set_and_owner_scoped() -> None:
    repo = MemoryTargetRepository()
    target = run(repo.create_target(USER_A, values()))
    set_id = uuid4()
    run(repo.record_questions(USER_A, [question(target.id, set_id)]))
    assert len(run(repo.questions_for_set(set_id, USER_A))) == 1
    assert run(repo.questions_for_set(set_id, USER_B)) == []
    # The same prompt can never appear twice in one practice set ...
    with pytest.raises(TargetConflict):
        run(repo.record_questions(USER_A, [question(target.id, set_id, position=2)]))
    # ... but a later practice may reuse it; the 30-day repeat window lives in the originality guard.
    later = uuid4()
    run(repo.record_questions(USER_A, [question(target.id, later)]))
    assert len(run(repo.questions_for_set(later, USER_A))) == 1
    with pytest.raises(LookupError):
        run(repo.record_questions(USER_B, [question(target.id, uuid4(), text="Another prompt that is long enough.")]))


def test_session_links_are_write_once() -> None:
    repo = MemoryTargetRepository()
    target = run(repo.create_target(USER_A, values()))
    other = run(repo.create_target(USER_A, values(geography_key="us", geography_label="US")))
    session_id = uuid4()
    link = run(repo.create_link(USER_A, TargetSessionLinkCreate(session_id=session_id, candidate_target_id=target.id, round_key="behavioural")))
    with pytest.raises(LinkAlreadyExists) as raised:
        run(repo.create_link(USER_A, TargetSessionLinkCreate(session_id=session_id, candidate_target_id=other.id, round_key="system_design")))
    assert raised.value.link == link
    assert run(repo.link_for_session(session_id, USER_A)).candidate_target_id == target.id
    assert run(repo.link_for_session(session_id, USER_B)) is None
    assert not hasattr(repo, "update_link")


def test_link_to_someone_elses_target_is_rejected() -> None:
    repo = MemoryTargetRepository()
    target = run(repo.create_target(USER_A, values()))
    with pytest.raises(LookupError):
        run(repo.create_link(USER_B, TargetSessionLinkCreate(session_id=uuid4(), candidate_target_id=target.id)))


# ------------------------------------------------------------------ Supabase repository (no network)


def supabase(handler):
    settings = Settings(next_public_supabase_url="https://example.invalid", supabase_service_role_key="service")
    return SupabaseTargetRepository(settings, client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def test_probe_reports_missing_tables_as_not_provisioned() -> None:
    def handler(request):
        if "target_session_links" in request.url.path:
            return httpx.Response(404, json={"code": "PGRST205", "message": "Could not find the table"})
        return httpx.Response(200, json=[])

    assert run(supabase(handler).probe()) is False


def test_probe_true_only_when_every_table_answers() -> None:
    seen = []

    def handler(request):
        seen.append(request.url.path.rsplit("/", 1)[-1])
        assert request.url.params["limit"] == "0"
        return httpx.Response(200, json=[])

    assert run(supabase(handler).probe()) is True
    assert sorted(seen) == ["candidate_targets", "generated_questions", "interview_blueprints", "target_session_links"]


def test_probe_transient_error_raises() -> None:
    assert_raises = pytest.raises(TargetsUnavailable)
    with assert_raises:
        run(supabase(lambda request: httpx.Response(500, json={})).probe())


def test_supabase_reads_always_filter_by_owner() -> None:
    params = []

    def handler(request):
        params.append(dict(request.url.params))
        return httpx.Response(200, json=[])

    repo = supabase(handler)
    run(repo.get_target(uuid4(), USER_A))
    run(repo.list_targets(USER_A))
    run(repo.link_for_session(uuid4(), USER_A))
    run(repo.links_for_target(uuid4(), USER_A))
    run(repo.questions_for_set(uuid4(), USER_A))
    assert params and all(p.get("user_id") == f"eq.{USER_A}" for p in params)


def test_supabase_link_insert_is_plain_insert_and_conflict_is_write_once() -> None:
    session_id, target_id = uuid4(), uuid4()
    existing = {
        "session_id": str(session_id), "user_id": str(USER_A), "candidate_target_id": str(target_id),
        "blueprint_id": None, "round_key": "behavioural", "competency_key": None, "prompt_set_id": None,
        "created_at": "2026-10-04T00:00:00+00:00",
    }
    methods = []

    def handler(request):
        methods.append((request.method, request.headers.get("prefer")))
        if request.method == "POST":
            body = json.loads(request.content)
            assert body["user_id"] == str(USER_A)
            return httpx.Response(409, json={"code": "23505"})
        return httpx.Response(200, json=[existing])

    with pytest.raises(LinkAlreadyExists):
        run(supabase(handler).create_link(USER_A, TargetSessionLinkCreate(session_id=session_id, candidate_target_id=target_id)))
    assert methods[0][0] == "POST" and "merge-duplicates" not in (methods[0][1] or "")
    assert all(method != "PATCH" for method, _ in methods)


# ------------------------------------------------------------------ capability


class Probe:
    def __init__(self, results):
        self.results, self.calls = list(results), 0

    async def __call__(self):
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_flag_off_is_disabled_without_probing() -> None:
    probe = Probe([True])
    assert run(TargetCapability(False, probe, ttl_seconds=60).state()) == TargetAvailability.DISABLED
    assert probe.calls == 0


def test_probe_result_is_cached_for_ttl() -> None:
    now = [0.0]
    probe = Probe([False, True])
    capability = TargetCapability(True, probe, ttl_seconds=60, clock=lambda: now[0])
    assert run(capability.state()) == TargetAvailability.UNAVAILABLE
    now[0] = 59
    assert run(capability.state()) == TargetAvailability.UNAVAILABLE
    assert probe.calls == 1
    now[0] = 61
    assert run(capability.state()) == TargetAvailability.AVAILABLE


def test_transient_probe_error_is_not_cached() -> None:
    probe = Probe([TargetsUnavailable("down"), True])
    capability = TargetCapability(True, probe, ttl_seconds=60, clock=lambda: 0.0)
    with pytest.raises(TargetsUnavailable):
        run(capability.state())
    assert run(capability.state()) == TargetAvailability.AVAILABLE


def test_settings_flag_defaults_off() -> None:
    assert Settings().loop2_targets_enabled is False
    assert Settings().loop2_target_probe_ttl_seconds > 0
