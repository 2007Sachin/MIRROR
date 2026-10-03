"use client";

import { Check, PencilSimple, Trash } from "@phosphor-icons/react";
import { FormEvent, useState } from "react";

import type { EvidenceEdit, EvidenceItem } from "@/lib/api-evidence";
import { onboardingCopy } from "@/lib/copy-onboarding";

const t = onboardingCopy.review;
const FIELDS = ["title", "detail", "outcome", "metric"] as const;
const LABELS = { title: t.titleField, detail: t.detail, outcome: t.outcome, metric: t.metric };

/** One thing found in the resume: keep it, fix it, or remove it. */
export function ReviewItem({ item, onSave }: { item: EvidenceItem; onSave: (values: EvidenceEdit) => Promise<boolean> }) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState(() => Object.fromEntries(FIELDS.map((field) => [field, item[field] ?? ""])) as Record<(typeof FIELDS)[number], string>);

  async function save(values: EvidenceEdit) {
    setSaving(true);
    const saved = await onSave(values);
    setSaving(false);
    if (saved) setEditing(false);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (draft.title.trim().length < 2) return;
    void save(Object.fromEntries(FIELDS.map((field) => [field, draft[field].trim() || null])) as EvidenceEdit);
  }

  if (item.status === "REMOVED") {
    return (
      <li className="op-item" data-status="REMOVED">
        <p className="op-muted"><s>{item.title}</s> {t.removed}</p>
        <button type="button" className="op-text op-target" disabled={saving} onClick={() => void save({ status: "PENDING" })}>{t.restore}</button>
      </li>
    );
  }

  if (editing) {
    return (
      <li className="op-item">
        <form onSubmit={submit} className="op-edit" aria-busy={saving}>
          {FIELDS.map((field) => (
            <label key={field}>
              <span>{LABELS[field]}</span>
              {field === "detail" ? (
                <textarea className="field" value={draft[field]} maxLength={2000} onChange={(event) => setDraft({ ...draft, [field]: event.target.value })} />
              ) : (
                <input className="field" value={draft[field]} maxLength={field === "metric" ? 200 : 500} required={field === "title"} minLength={field === "title" ? 2 : undefined} onChange={(event) => setDraft({ ...draft, [field]: event.target.value })} />
              )}
            </label>
          ))}
          <div className="op-action-group">
            <button type="button" className="op-text op-target" onClick={() => setEditing(false)} disabled={saving}>{t.cancel}</button>
            <button type="submit" className="button-secondary op-target" disabled={saving}>{saving ? t.saving : t.save}</button>
          </div>
        </form>
      </li>
    );
  }

  const kept = item.status === "APPROVED";
  return (
    <li className="op-item" data-status={item.status}>
      <div className="op-item-body">
        <p className="op-strong">{item.title}</p>
        {item.detail && <p>{item.detail}</p>}
        {(item.outcome || item.metric) && (
          <dl className="op-facts">
            {item.outcome && <div><dt>{t.outcome}</dt><dd>{item.outcome}</dd></div>}
            {item.metric && <div><dt>{t.metric}</dt><dd>{item.metric}</dd></div>}
          </dl>
        )}
        <p className="op-source">
          {item.source_label}
          {item.edited && <span className="op-chip">{t.edited}</span>}
          {kept && <span className="op-chip"><Check size={13} aria-hidden="true" /> {t.kept}</span>}
        </p>
      </div>
      <div className="op-item-actions">
        {!kept && (
          <button type="button" className="op-text op-target" disabled={saving} onClick={() => void save({ status: "APPROVED" })}>
            <Check size={15} aria-hidden="true" /> {t.keep}
          </button>
        )}
        <button type="button" className="op-text op-target" disabled={saving} onClick={() => setEditing(true)} aria-label={`${t.edit}: ${item.title}`}>
          <PencilSimple size={15} aria-hidden="true" /> {t.edit}
        </button>
        <button type="button" className="op-text op-target" disabled={saving} onClick={() => void save({ status: "REMOVED" })} aria-label={`${t.remove}: ${item.title}`}>
          <Trash size={15} aria-hidden="true" /> {t.remove}
        </button>
      </div>
    </li>
  );
}
