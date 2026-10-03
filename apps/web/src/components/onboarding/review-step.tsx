"use client";

import { ArrowLeft, ArrowRight } from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";

import { ReviewItem } from "@/components/onboarding/review-item";
import { StepHeading, type Report } from "@/components/onboarding/shared";
import { approveEvidence, getEvidence, updateEvidence, type EvidenceEdit, type EvidenceKind, type EvidenceList } from "@/lib/api-evidence";
import { onboardingCopy } from "@/lib/copy-onboarding";

const t = onboardingCopy.review;
// Top achievements first, then projects, responsibilities and skills.
const ORDER: EvidenceKind[] = ["ACHIEVEMENT", "PROJECT", "RESPONSIBILITY", "SKILL"];
const POLL_MS = 4000;

type Loaded = EvidenceList | "UNAVAILABLE" | "ERROR" | null;

export function ReviewStep({ report, onBack, onDone }: { report: Report; onBack: () => void; onDone: () => Promise<void> }) {
  const [list, setList] = useState<Loaded>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setList(await getEvidence());
    } catch (reason) {
      setList("ERROR");
      report(t.loadError, reason);
    }
  }, [report]);

  useEffect(() => {
    void load();
  }, [load]);

  // Reading takes a little while: check again calmly until it is done.
  const reading = typeof list === "object" && list?.state === "READING";
  useEffect(() => {
    if (!reading) return;
    const timer = window.setTimeout(() => void load(), POLL_MS);
    return () => window.clearTimeout(timer);
  }, [reading, list, load]);

  async function save(id: string, values: EvidenceEdit) {
    try {
      const updated = await updateEvidence(id, values);
      setList((current) => typeof current === "object" && current
        ? { ...current, items: current.items.map((item) => (item.id === id ? updated : item)) }
        : current);
      report("");
      return true;
    } catch (reason) {
      report(t.saveError, reason);
      return false;
    }
  }

  async function finish() {
    setBusy(true);
    report("");
    try {
      const pending = typeof list === "object" && list ? list.items.filter((item) => item.status === "PENDING").map((item) => item.id) : [];
      if (pending.length) await approveEvidence(pending);
      await onDone();
    } catch (reason) {
      report(t.saveError, reason);
    } finally {
      setBusy(false);
    }
  }

  const back = (
    <button type="button" className="ob-back op-target" onClick={onBack} disabled={busy}>
      <ArrowLeft size={17} aria-hidden="true" /> {t.back}
    </button>
  );
  const proceed = (label: string) => (
    <button type="button" className="button-primary op-target" onClick={() => void finish()} disabled={busy}>
      {busy ? t.saving : label} <ArrowRight size={18} aria-hidden="true" />
    </button>
  );

  if (list === null || reading) {
    return (
      <section className="ob-step" aria-busy="true">
        <StepHeading title={t.readingTitle} intro={t.readingBody} />
        <div className="op-reading" role="status" aria-live="polite"><span aria-hidden="true" /></div>
        <div className="ob-actions">{back}<span /></div>
      </section>
    );
  }

  if (list === "ERROR") {
    return (
      <section className="ob-step">
        <StepHeading title={t.title} />
        <div className="ob-actions">{back}<button type="button" className="button-primary op-target" onClick={() => { setList(null); void load(); }}>{t.retry}</button></div>
      </section>
    );
  }

  if (list === "UNAVAILABLE" || list.state === "UNREADABLE" || list.state === "NO_RESUME" || !list.items.length) {
    const copy = list === "UNAVAILABLE"
      ? { title: t.unavailableTitle, body: t.unavailableBody }
      : list.state === "UNREADABLE"
        ? { title: t.unreadableTitle, body: t.unreadableBody }
        : list.state === "NO_RESUME"
          ? { title: t.noResumeTitle, body: t.noResumeBody }
          : { title: t.emptyTitle, body: t.emptyBody };
    const needsResume = list !== "UNAVAILABLE" && list.state === "NO_RESUME";
    const canRetryUpload = list !== "UNAVAILABLE" && list.state === "UNREADABLE";
    return (
      <section className="ob-step">
        <StepHeading title={copy.title} intro={copy.body} />
        <div className="ob-actions">
          {back}
          <div className="op-action-group">
            {canRetryUpload && <button type="button" className="button-secondary op-target" onClick={onBack} disabled={busy}>{t.reupload}</button>}
            {needsResume
              ? <button type="button" className="button-primary op-target" onClick={onBack}>{t.addResume}</button>
              : proceed(canRetryUpload ? t.continueAnyway : t.continue)}
          </div>
        </div>
      </section>
    );
  }

  const groups = ORDER.map((kind) => ({ kind, items: list.items.filter((item) => item.kind === kind) })).filter((group) => group.items.length);
  return (
    <section className="ob-step">
      <StepHeading title={t.title} intro={t.intro} />
      {groups.map((group) => (
        <section key={group.kind} className="op-group" aria-labelledby={`op-group-${group.kind}`}>
          <h2 id={`op-group-${group.kind}`}>{t.groups[group.kind]}</h2>
          <ul className="op-list">
            {group.items.map((item) => <ReviewItem key={`${item.id}:${item.updated_at}`} item={item} onSave={(values) => save(item.id, values)} />)}
          </ul>
        </section>
      ))}
      <div className="ob-actions">{back}{proceed(t.useInPlan)}</div>
    </section>
  );
}
