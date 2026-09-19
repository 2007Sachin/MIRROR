"use client";

import { FileArrowUp, SpinnerGap, WarningCircle, X } from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";

import { EVIDENCE_CATEGORIES, evidenceCategory } from "@/components/workspace/evidence-types";
import type { EvidenceCategory, EvidenceDetail } from "@/lib/api";

function useModalDialog(ref: React.RefObject<HTMLDialogElement | null>) {
  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
    return () => { if (dialog?.open) dialog.close(); };
  }, [ref]);
}

export function EvidenceUploadDialog({
  replacing,
  busy,
  progress,
  error,
  onClose,
  onSubmit,
}: {
  replacing?: EvidenceDetail | null;
  busy: boolean;
  progress: number;
  error: string;
  onClose: () => void;
  onSubmit: (file: File, values: { title: string; evidence_category: EvidenceCategory; context_note: string }) => Promise<void>;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState(replacing?.document.title || "");
  const [category, setCategory] = useState<EvidenceCategory>(replacing ? evidenceCategory(replacing.document) : "OTHER");
  const [context, setContext] = useState(replacing?.document.context_note || "");
  useModalDialog(dialogRef);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    await onSubmit(file, { title: title.trim() || file.name.replace(/\.[^.]+$/, ""), evidence_category: category, context_note: context });
  }

  return (
    <dialog ref={dialogRef} className="ws-dialog" onCancel={(event) => { event.preventDefault(); if (!busy) onClose(); }}>
      <form className="ws-dialog-panel scale-in-once" onSubmit={submit}>
        <header className="ws-dialog-header">
          <div><p className="ws-eyebrow">{replacing ? "New evidence version" : "Add evidence"}</p><h2 className="display">{replacing ? "Replace the current file" : "Give Mirror evidence to work from"}</h2></div>
          <button type="button" onClick={onClose} disabled={busy} aria-label="Close"><X size={19} /></button>
        </header>
        <div className="ws-dialog-body">
          {replacing ? <div className="ws-callout"><strong>Historical versions stay intact.</strong><p>Diagnostics already using version {replacing.document.version_number} will keep it. The replacement becomes the version available to future diagnostics.</p></div> : null}
          <label className="ws-file-drop">
            <FileArrowUp size={24} />
            <strong>{file ? file.name : "Choose a PDF or DOCX file"}</strong>
            <span>Mirror validates the file before adding it</span>
            <input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => { const next = event.target.files?.[0] ?? null; setFile(next); if (next && !title) setTitle(next.name.replace(/\.[^.]+$/, "")); }} required />
          </label>
          <div className="ws-field-grid">
            <label><span>Evidence title</span><input className="field" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={160} required /></label>
            <label><span>Category</span><select className="field" value={category} onChange={(event) => setCategory(event.target.value as EvidenceCategory)}>{EVIDENCE_CATEGORIES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
          </div>
          <label><span>Context for Mirror <small>Optional</small></span><textarea className="field" value={context} onChange={(event) => setContext(event.target.value)} maxLength={4000} rows={4} placeholder="Add ownership, scope, dates, or outcomes the file does not make clear." /></label>
          {busy ? (
            <div className="ws-progress-bar" role="progressbar" aria-label="Evidence upload progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}>
              <i style={{ "--ws-progress": `${progress}%` } as React.CSSProperties} />
              <span>{progress < 100 ? `Uploading ${progress}%` : "Refreshing evidence"}</span>
            </div>
          ) : null}
          {error ? <p className="ws-dialog-error" role="alert">{error}</p> : null}
        </div>
        <footer className="ws-dialog-footer">
          <button type="button" className="button-secondary" onClick={onClose} disabled={busy}>Cancel</button>
          <button type="submit" className="button-primary" disabled={busy || !file || !title.trim()}>{busy ? <SpinnerGap className="interview-spinner" size={17} /> : null}{replacing ? "Replace file" : "Add evidence"}</button>
        </footer>
      </form>
    </dialog>
  );
}

export function EvidenceRemoveDialog({
  items,
  busy,
  error,
  onClose,
  onConfirm,
}: {
  items: EvidenceDetail[];
  busy: boolean;
  error: string;
  onClose: () => void;
  onConfirm: () => Promise<void>;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  useModalDialog(dialogRef);
  const active = items.reduce((sum, item) => sum + item.usage.active_diagnostic_count, 0);
  const completed = items.reduce((sum, item) => sum + item.usage.completed_diagnostic_count, 0);

  return (
    <dialog ref={dialogRef} className="ws-dialog" onCancel={(event) => { event.preventDefault(); if (!busy) onClose(); }}>
      <div className="ws-dialog-panel scale-in-once">
        <header className="ws-dialog-header">
          <span className="ws-dialog-warning-icon"><WarningCircle size={22} /></span>
          <div><p className="ws-eyebrow">Remove from library</p><h2 className="display">{items.length === 1 ? "Remove this evidence?" : `Remove ${items.length} evidence items?`}</h2></div>
          <button type="button" onClick={onClose} disabled={busy} aria-label="Close"><X size={19} /></button>
        </header>
        <div className="ws-dialog-body">
          <p>Mirror will stop offering {items.length === 1 ? "this item" : "these items"} for future diagnostics. The original files and historical diagnostic references will be retained.</p>
          {active || completed ? <div className="ws-callout"><strong>This evidence is being used.</strong><p>{active ? `${active} active diagnostic ${active === 1 ? "uses" : "use"} the existing version. ` : ""}{completed ? `${completed} completed diagnostic ${completed === 1 ? "retains" : "retain"} its historical findings.` : ""}</p></div> : null}
          <ul>{items.slice(0, 5).map((item) => <li key={item.document.id}>{item.document.title || item.document.original_filename || "Professional evidence"}</li>)}</ul>
          {error ? <p className="ws-dialog-error" role="alert">{error}</p> : null}
        </div>
        <footer className="ws-dialog-footer">
          <button type="button" className="button-secondary" onClick={onClose} disabled={busy}>Cancel</button>
          <button type="button" className="ws-destructive-button" onClick={() => void onConfirm()} disabled={busy}>{busy ? <SpinnerGap className="interview-spinner" size={17} /> : null} Remove from library</button>
        </footer>
      </div>
    </dialog>
  );
}
