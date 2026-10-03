"use client";

import "@/styles/onboarding-plan.css";

import { useCallback, useEffect, useState } from "react";

import { ReviewItem } from "@/components/onboarding/review-item";
import { PageAlert, Section } from "@/components/workspace/page-shell";
import { approveEvidence, getEvidence, updateEvidence, type EvidenceEdit, type EvidenceKind, type EvidenceList } from "@/lib/api-evidence";
import { onboardingCopy } from "@/lib/copy-onboarding";
import { reviewedExamplesCopy as t } from "@/lib/copy-plan";

// Same order as onboarding review: achievements first, then projects, responsibilities and skills.
const ORDER: EvidenceKind[] = ["ACHIEVEMENT", "PROJECT", "RESPONSIBILITY", "SKILL"];
const POLL_MS = 4000;

/** Review what Mirror found in your resume after onboarding. Linked from My plan as /experience#review. */
export function ReviewedExamples() {
  const [list, setList] = useState<EvidenceList | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setList(await getEvidence());
      setLoadError(false);
    } catch {
      setLoadError(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const reading = list?.state === "READING";
  useEffect(() => {
    if (!reading) return;
    const timer = window.setTimeout(() => void load(), POLL_MS);
    return () => window.clearTimeout(timer);
  }, [reading, list, load]);

  async function save(id: string, values: EvidenceEdit) {
    try {
      const updated = await updateEvidence(id, values);
      setList((current) => current && { ...current, items: current.items.map((item) => (item.id === id ? updated : item)) });
      setSaveError("");
      return true;
    } catch {
      setSaveError(t.saveError);
      return false;
    }
  }

  const pending = list?.items.filter((item) => item.status === "PENDING").map((item) => item.id) ?? [];

  async function keepAll() {
    setBusy(true);
    setSaveError("");
    try {
      await approveEvidence(pending);
      await load();
    } catch {
      setSaveError(t.saveError);
    } finally {
      setBusy(false);
    }
  }

  const groups = ORDER.map((kind) => ({ kind, items: list?.items.filter((item) => item.kind === kind) ?? [] })).filter((group) => group.items.length);
  const message = loadError ? null
    : !list || reading ? t.reading
      : list.state === "UNREADABLE" ? t.unreadable
        : !list.items.length ? t.empty
          : null;

  return (
    <div id="review">
      <Section
        id="experience-review"
        label={t.label}
        title={t.title}
        body={t.body}
        action={pending.length ? (
          <button type="button" className="dh-primary-action is-quiet" disabled={busy} onClick={() => void keepAll()}>
            {t.keepAll(pending.length)}
          </button>
        ) : undefined}
      >
        {loadError ? <PageAlert message={t.loadError} onRetry={() => void load()} retryLabel={t.retry} /> : null}
        {saveError ? <PageAlert message={saveError} /> : null}
        {message ? <p className="dh-review-empty" role="status">{message}</p> : null}
        {!message && !loadError ? groups.map((group) => (
          <section key={group.kind} className="op-group" aria-labelledby={`review-group-${group.kind}`}>
            <h3 id={`review-group-${group.kind}`}>{onboardingCopy.review.groups[group.kind]}</h3>
            <ul className="op-list">
              {group.items.map((item) => <ReviewItem key={`${item.id}:${item.updated_at}`} item={item} onSave={(values) => save(item.id, values)} />)}
            </ul>
          </section>
        )) : null}
      </Section>
    </div>
  );
}
