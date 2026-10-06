"use client";

import "@/styles/practice-reflect.css";

import { ArrowRight, Check, Plus } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useRef, useState } from "react";

import { PageAlert, PageHeader, PageLoading, PageShell, usePageData } from "@/components/workspace/page-shell";
import { getActiveRole, type ActiveRoleState } from "@/lib/api-active-role";
import { ApiError, mirrorApi, type DashboardResponse, type Onboarding, type PracticeChoice, type PracticeFocusKey, type PracticeMode, type Story } from "@/lib/api";
import { getTarget, startRoundPractice, type TargetView } from "@/lib/api-targets";
import { practice, practiceFocus, startPractice as t } from "@/lib/copy";
import { preCheck } from "@/lib/copy-practice";
import { roundLabel, targetCopy, targetLine } from "@/lib/copy-targets";
import { newSessionHref, practiceOptions, type PracticeOption } from "@/lib/dashboard-view";
import { MODES, briefHref, choiceFrom, choiceIsComplete, focusFor, modeCopy, sameRole, setupHref } from "@/lib/practice-view";
import { canStartDirectly, createPractice } from "@/lib/start-practice";
import { documentsForRoundRole } from "@/lib/round-practice-documents";

type StartData = { workspace: DashboardResponse; onboarding: Onboarding; story: Story | null; active: ActiveRoleState | null; target: TargetView | null };

async function loadStart(storyId: string | null, targetId: string | null): Promise<StartData> {
  const [workspace, onboarding, story, active, target] = await Promise.all([
    mirrorApi.dashboard(),
    mirrorApi.onboarding(),
    storyId ? mirrorApi.story(storyId).catch(() => null) : Promise.resolve(null),
    // Without the active role the page simply asks which role, as before.
    getActiveRole().catch(() => null),
    // A round practice names its target on the check; without it the line is simply shorter.
    targetId ? getTarget(targetId).then((result) => result.target).catch(() => null) : Promise.resolve(null),
  ]);
  return { workspace, onboarding, story: story && !story.archived_at ? story : null, active, target };
}

const ROUND_MODES: PracticeMode[] = ["QUICK_DRILL", "FOCUSED_PRACTICE"];

type PickedRole = { role: string; id: string | null };

/**
 * The pre-practice check. Role (the active role unless one was asked for), format, focus and
 * expected length are all shown first; "Start practice" is the only moment a practice is created.
 */
export function StartPractice() {
  const router = useRouter();
  const params = useSearchParams();
  // Practising one chosen story: only a short story practice, and only for a role that can start here.
  const storyId = params.get("story");
  // Practising one round of an interview target (from My plan): role focus, the round's own prompts.
  const targetId = params.get("target");
  const roundKey = params.get("round");
  const round = !storyId && targetId && roundKey && roundLabel(roundKey) ? { targetId, key: roundKey, label: roundLabel(roundKey)! } : null;
  const { state, data, error, reload } = usePageData(() => loadStart(storyId, round?.targetId ?? null), practice.errors.load, [storyId, round?.targetId]);

  const paramRole = params.get("role")?.trim() || null;
  // undefined: nothing chosen yet, so the active role is used; null: choosing a role.
  const [picked, setPicked] = useState<PickedRole | null | undefined>(
    paramRole ? { role: paramRole, id: params.get("role_profile_id") } : undefined,
  );
  const [choice, setChoice] = useState<PracticeChoice>(() =>
    storyId
      ? { mode: params.get("mode") === "FOCUSED_PRACTICE" ? "FOCUSED_PRACTICE" : "QUICK_DRILL", focus: "story", theme: null }
      : round
        ? { mode: params.get("mode") === "QUICK_DRILL" ? "QUICK_DRILL" : "FOCUSED_PRACTICE", focus: "role", theme: round.label }
        : choiceFrom(params.get("mode"), params.get("focus"), params.get("theme")),
  );
  const [busy, setBusy] = useState(false);
  const [startError, setStartError] = useState("");
  const roles = data?.active?.roles ?? [];
  const fallback = params.get("role_profile_id");
  const defaultRole = (fallback ? roles.find((item) => item.role_profile_id === fallback) : null) ?? data?.active?.role ?? null;
  const chosen: PickedRole | null =
    picked === undefined ? (defaultRole ? { role: defaultRole.target_role, id: defaultRole.role_profile_id } : null) : picked;
  const role = chosen?.role ?? null;
  const roleProfileId = chosen?.id ?? null;
  const idempotencyKey = useRef<string>(crypto.randomUUID());

  const options = useMemo(() => {
    if (!data) return [];
    const sessions = [data.workspace.current, ...data.workspace.previous].filter((item) => item !== null);
    return practiceOptions(sessions, data.onboarding);
  }, [data]);

  const step = role ? 2 : 1;

  function pickRole(name: string) {
    setPicked({ role: name, id: roles.find((item) => sameRole(item.target_role, name))?.role_profile_id ?? null });
  }

  function chooseMode(mode: PracticeMode) {
    setChoice((current) => ({ ...current, mode, focus: mode === "FULL_INTERVIEW" ? null : current.focus }));
  }

  const modes = storyId ? MODES.filter((mode) => mode !== "FULL_INTERVIEW") : round ? ROUND_MODES : MODES;

  function chooseFocus(focus: PracticeFocusKey) {
    // A theme belongs to role-specific practice only, and only the one that was offered.
    setChoice((current) => ({ ...current, focus, theme: focus === "role" ? current.theme : null }));
  }

  async function begin() {
    if (!role || !data || !choiceIsComplete(choice)) return;
    setBusy(true);
    setStartError("");
    try {
      if (round) {
        // The round's guarded prompts are stored and the session linked by the target service;
        // documents and preparation then follow the usual practice path.
        const started = await startRoundPractice(round.targetId, round.key, choice.mode === "QUICK_DRILL" ? "QUICK_DRILL" : "FOCUSED_PRACTICE", idempotencyKey.current);
        const documentIds = documentsForRoundRole(data.target?.role_profile_id, data.onboarding);

        if (documentIds.length) await mirrorApi.linkSessionDocuments(started.session.id, documentIds);
        await mirrorApi.prepare(started.session.id);
        router.push(briefHref(started.session.id));
        return;
      }
      const direct = canStartDirectly(role, data.onboarding) && (!roleProfileId || roleProfileId === data.onboarding.onboarding_role_profile_id);
      if (storyId) {
        // Never fall through to the setup flow here: it would quietly drop the chosen story.
        if (!data.story) setStartError(t.story.missing);
        else if (!direct) setStartError(t.story.roleNeeded);
        else router.push(briefHref(await createPractice(role, data.onboarding, choice, roleProfileId, idempotencyKey.current, [data.story.id])));
        if (!data.story || !direct) setBusy(false);
        return;
      }
      if (direct) {
        router.push(briefHref(await createPractice(role, data.onboarding, choice, roleProfileId, idempotencyKey.current)));
        return;
      }
      router.push(setupHref(role, choice, roleProfileId));
    } catch (reason) {
      const code = reason instanceof ApiError ? reason.code : undefined;
      const quiet = reason instanceof ApiError && (reason.status === 503 || reason.status === 404);
      setStartError(code === "SHORT_PACK" ? targetCopy.practice.shortPack : round && quiet ? targetCopy.practice.unavailable : t.focusStep.failed);
      setBusy(false);
    }
  }

  return (
    <PageShell>
      <PageHeader
        eyebrow={t.eyebrow}
        title={step === 1 ? t.roleStep.title : t.focusStep.title}
        intro={step === 1 ? t.roleStep.body : t.focusStep.body}
        back={step === 1 ? { href: "/practice", label: practice.eyebrow } : undefined}
      />
      <p className="dh-step-count" aria-live="polite">{t.stepOf(step, 2)}</p>

      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}

      {state === "ready" && step === 1 ? (
        <div className="dh-choice-list">
          {options.length ? (
            options.map((option) => (
              <button key={option.role} type="button" onClick={() => pickRole(option.role)}>
                <span className="dh-choice-copy">
                  <strong>{option.role}</strong>
                  <small>{describe(option)}</small>
                </span>
                <ArrowRight size={16} aria-hidden="true" />
              </button>
            ))
          ) : (
            <p className="dh-review-empty">{t.roleStep.empty}</p>
          )}
          <Link href={newSessionHref()} className="dh-choice-add">
            <span className="dh-choice-copy">
              <strong>
                <Plus size={15} aria-hidden="true" /> {t.roleStep.another}
              </strong>
              <small>{t.roleStep.anotherBody}</small>
            </span>
            <ArrowRight size={16} aria-hidden="true" />
          </Link>
        </div>
      ) : null}

      {state === "ready" && step === 2 && role ? (
        <>
          <p className="dh-chosen-role">
            {role}{" "}
            <button type="button" className="dh-text-action" onClick={() => setPicked(null)} disabled={busy}>
              {preCheck.changeRole}
            </button>
          </p>

          <fieldset className="dh-choice-list is-focus">
            <legend className="dh-subhead">{t.focusStep.howLabel}</legend>
            {modes.map((mode) => (
              <label key={mode} className={choice.mode === mode ? "is-selected" : ""}>
                <input type="radio" name="practice-mode" value={mode} checked={choice.mode === mode} onChange={() => chooseMode(mode)} disabled={busy} />
                <span className="dh-choice-copy">
                  <strong>{modeCopy(mode).title}</strong>
                  <small>{modeCopy(mode).body}</small>
                </span>
                <span className="dh-focus-tag is-quiet">{modeCopy(mode).length}</span>
                <span className="dh-choice-tick" aria-hidden="true"><Check size={15} /></span>
              </label>
            ))}
          </fieldset>

          {storyId ? (
            <div className="dh-guidance dh-practice-story">
              <p className="dh-subhead">{t.story.label}</p>
              {data?.story ? <strong>{data.story.title}</strong> : <p>{t.story.missing}</p>}
              <p className="dh-fine-print">{t.story.body}</p>
            </div>
          ) : round ? null : choice.mode !== "FULL_INTERVIEW" ? (
            <fieldset className="dh-choice-list is-focus">
              <legend className="dh-subhead">{t.focusStep.whatLabel}</legend>
              {practiceFocus.options.map((option) => (
                <label key={option.key} className={choice.focus === option.key ? "is-selected" : ""}>
                  <input type="radio" name="practice-focus" value={option.key} checked={choice.focus === option.key} onChange={() => chooseFocus(option.key)} disabled={busy} />
                  <span className="dh-choice-copy">
                    <strong>{option.key === "role" && choice.theme ? choice.theme : option.title}</strong>
                    <small>{option.body}</small>
                  </span>
                  <span />
                  <span className="dh-choice-tick" aria-hidden="true"><Check size={15} /></span>
                </label>
              ))}
            </fieldset>
          ) : null}

          <section className="pr-check" aria-labelledby="practice-check-title">
            <h2 id="practice-check-title">{preCheck.title}</h2>
            <p>{preCheck.body}</p>
            <dl>
              <div>
                <dt>{preCheck.role}</dt>
                <dd>{role}</dd>
              </div>
              <div>
                <dt>{preCheck.format}</dt>
                <dd>{modeCopy(choice.mode).title}</dd>
              </div>
              <div>
                <dt>{preCheck.focus}</dt>
                <dd>
                  {round
                    ? targetCopy.practice.roundFocus(round.label, data?.target ? targetLine(data.target) : null)
                    : focusLabel(choice, storyId ? data?.story?.title ?? null : null)}
                </dd>
              </div>
              <div>
                <dt>{preCheck.length}</dt>
                <dd>{modeCopy(choice.mode).length}</dd>
              </div>
            </dl>
          </section>

          {startError ? <PageAlert message={startError} /> : null}
          <div className="dh-action-row">
            <button className="dh-primary-action" type="button" onClick={() => void begin()} disabled={busy || !choiceIsComplete(choice)} aria-busy={busy}>
              {busy ? t.focusStep.preparing : t.focusStep.begin}
              {busy ? null : <ArrowRight size={17} aria-hidden="true" />}
            </button>
          </div>
        </>
      ) : null}
    </PageShell>
  );
}

function focusLabel(choice: PracticeChoice, story: string | null) {
  if (story) return story;
  if (choice.mode === "FULL_INTERVIEW") return preCheck.wholeInterview;
  if (choice.focus === "role" && choice.theme) return choice.theme;
  return focusFor(choice.focus)?.title ?? preCheck.chooseFocus;
}

function describe(option: PracticeOption) {
  if (option.quickStart) return t.roleStep.ready;
  return option.description;
}
