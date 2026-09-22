"use client";

import { ArrowRight, Check, Plus } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { PageAlert, PageHeader, PageLoading, PageShell, usePageData } from "@/components/workspace/page-shell";
import { mirrorApi, type DashboardResponse, type Onboarding, type PracticeChoice, type PracticeFocusKey, type PracticeMode } from "@/lib/api";
import { practice, practiceFocus, startPractice as t } from "@/lib/copy";
import { newSessionHref, practiceOptions, type PracticeOption } from "@/lib/dashboard-view";
import { MODES, briefHref, choiceFrom, choiceIsComplete, modeCopy, setupHref } from "@/lib/practice-view";
import { canStartDirectly, createPractice } from "@/lib/start-practice";

type StartData = { workspace: DashboardResponse; onboarding: Onboarding };

async function loadStart(): Promise<StartData> {
  const [workspace, onboarding] = await Promise.all([mirrorApi.dashboard(), mirrorApi.onboarding()]);
  return { workspace, onboarding };
}

export function StartPractice() {
  const router = useRouter();
  const params = useSearchParams();
  const { state, data, error, reload } = usePageData(loadStart, practice.errors.load);

  const [role, setRole] = useState<string | null>(params.get("role")?.trim() || null);
  const [choice, setChoice] = useState<PracticeChoice>(() =>
    choiceFrom(params.get("mode"), params.get("focus"), params.get("theme")),
  );
  const [busy, setBusy] = useState(false);
  const [startError, setStartError] = useState("");

  const options = useMemo(() => {
    if (!data) return [];
    const sessions = [data.workspace.current, ...data.workspace.previous].filter((item) => item !== null);
    return practiceOptions(sessions, data.onboarding);
  }, [data]);

  const step = role ? 2 : 1;

  function chooseMode(mode: PracticeMode) {
    setChoice((current) => ({ ...current, mode, focus: mode === "FULL_INTERVIEW" ? null : current.focus }));
  }

  function chooseFocus(focus: PracticeFocusKey) {
    // A theme belongs to role-specific practice only, and only the one that was offered.
    setChoice((current) => ({ ...current, focus, theme: focus === "role" ? current.theme : null }));
  }

  async function begin() {
    if (!role || !data || !choiceIsComplete(choice)) return;
    setBusy(true);
    setStartError("");
    try {
      if (canStartDirectly(role, data.onboarding)) {
        router.push(briefHref(await createPractice(role, data.onboarding, choice)));
        return;
      }
      router.push(setupHref(role, choice));
    } catch {
      setStartError(t.focusStep.failed);
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
              <button key={option.role} type="button" onClick={() => setRole(option.role)}>
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
            <button type="button" className="dh-text-action" onClick={() => setRole(null)} disabled={busy}>
              {t.back}
            </button>
          </p>

          <fieldset className="dh-choice-list is-focus">
            <legend className="dh-subhead">{t.focusStep.howLabel}</legend>
            {MODES.map((mode) => (
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

          {choice.mode !== "FULL_INTERVIEW" ? (
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

          {startError ? <PageAlert message={startError} /> : null}
          <div className="dh-action-row">
            <button className="dh-primary-action" type="button" onClick={() => void begin()} disabled={busy || !choiceIsComplete(choice)}>
              {busy ? t.focusStep.preparing : t.focusStep.begin}
              {busy ? null : <ArrowRight size={17} aria-hidden="true" />}
            </button>
            <span className="dh-action-meta">{modeCopy(choice.mode).length}</span>
          </div>
        </>
      ) : null}
    </PageShell>
  );
}

function describe(option: PracticeOption) {
  if (option.quickStart) return t.roleStep.ready;
  return option.description;
}
