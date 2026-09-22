"use client";

import { ArrowRight, Check, Plus } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import {
  PageAlert,
  PageHeader,
  PageLoading,
  PageShell,
  usePageData,
} from "@/components/workspace/page-shell";
import { mirrorApi, type DashboardResponse, type Onboarding } from "@/lib/api";
import { practice, practiceFocus, startPractice as t } from "@/lib/copy";
import { newSessionHref, practiceOptions, type PracticeOption } from "@/lib/dashboard-view";
import { briefHref, focusFor, isFocusKey, otherFocusOptions, recommendedFocus, setupHref } from "@/lib/practice-view";
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

  const requestedRole = params.get("role")?.trim() || "";
  const requestedFocus = params.get("focus");
  const [role, setRole] = useState<string | null>(requestedRole || null);
  const [focus, setFocus] = useState(isFocusKey(requestedFocus) ? requestedFocus : recommendedFocus().key);
  const [busy, setBusy] = useState(false);
  const [startError, setStartError] = useState("");

  const options = useMemo(() => {
    if (!data) return [];
    const sessions = [data.workspace.current, ...data.workspace.previous].filter((item) => item !== null);
    return practiceOptions(sessions, data.onboarding);
  }, [data]);

  const chosen = role ?? null;
  const step = chosen ? 2 : 1;

  async function begin() {
    if (!chosen || !data) return;
    setBusy(true);
    setStartError("");
    try {
      if (canStartDirectly(chosen, data.onboarding)) {
        const sessionId = await createPractice(chosen, data.onboarding);
        router.push(briefHref(sessionId, focus));
        return;
      }
      router.push(setupHref(chosen, focus));
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

      {state === "ready" && step === 2 && chosen ? (
        <>
          <p className="dh-chosen-role">
            {chosen}{" "}
            <button type="button" className="dh-text-action" onClick={() => setRole(null)} disabled={busy}>
              {t.back}
            </button>
          </p>

          <fieldset className="dh-choice-list is-focus">
            <legend className="sr-only">{t.focusStep.title}</legend>
            {[recommendedFocus(), ...otherFocusOptions()].map((option) => (
              <label key={option.key} className={focus === option.key ? "is-selected" : ""}>
                <input
                  type="radio"
                  name="practice-focus"
                  value={option.key}
                  checked={focus === option.key}
                  onChange={() => setFocus(option.key)}
                  disabled={busy}
                />
                <span className="dh-choice-copy">
                  <strong>{option.title}</strong>
                  <small>{option.body}</small>
                </span>
                {"recommended" in option && option.recommended ? (
                  <span className="dh-focus-tag">{practice.recommended}</span>
                ) : null}
                <span className="dh-choice-tick" aria-hidden="true">
                  <Check size={15} />
                </span>
              </label>
            ))}
          </fieldset>

          <p className="dh-fine-print">{practiceFocus.note}</p>
          {startError ? <PageAlert message={startError} /> : null}

          <div className="dh-action-row">
            <button className="dh-primary-action" type="button" onClick={() => void begin()} disabled={busy}>
              {busy ? t.focusStep.preparing : t.focusStep.begin}
              {busy ? null : <ArrowRight size={17} aria-hidden="true" />}
            </button>
            <span className="dh-action-meta">{focusFor(focus).title}</span>
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
