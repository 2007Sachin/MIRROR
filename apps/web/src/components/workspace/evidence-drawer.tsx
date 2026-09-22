"use client";

import {
  ArrowCounterClockwise,
  DownloadSimple,
  FileText,
  SpinnerGap,
  Swap,
  Trash,
  X,
} from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";

import { EVIDENCE_CATEGORIES, evidenceCategory, evidenceCategoryLabel } from "@/components/workspace/evidence-types";
import { formatWorkspaceDate } from "@/components/workspace/workspace-utils";
import { mirrorApi, type EvidenceCategory, type EvidenceDetail, type ResumeAnalysis } from "@/lib/api";

export type EvidenceDrawerMode = "view" | "edit" | "category" | "context";

function MirrorUnderstanding({ detail }: { detail: EvidenceDetail }) {
  const [analysis, setAnalysis] = useState<ResumeAnalysis | null>(null);
  const { document } = detail;

  useEffect(() => {
    let active = true;
    if (document.document_type !== "RESUME") return;
    void mirrorApi.resumeAnalysis(document.id)
      .then((value) => { if (active) setAnalysis(value); })
      .catch(() => undefined);
    return () => { active = false; };
  }, [document.document_type, document.id]);

  const skills = analysis?.output?.skills?.slice(0, 6).map((skill) => skill.name) ?? [];
  const projects = analysis?.output?.projects?.slice(0, 3).map((project) => project.project_name) ?? [];
  const excerpt = document.raw_text?.trim().slice(0, 900);
  if (!analysis && !excerpt) {
    return <p className="ws-muted-copy">Mirror hasn't put together a summary of this version yet.</p>;
  }
  return (
    <div className="ws-understanding">
      {skills.length ? <p><strong>Skills found</strong>{skills.join(" · ")}</p> : null}
      {projects.length ? <p><strong>Projects found</strong>{projects.join(" · ")}</p> : null}
      {excerpt ? <p><strong>Document excerpt</strong>{excerpt}{document.raw_text && document.raw_text.length > 900 ? "…" : ""}</p> : null}
    </div>
  );
}

export function EvidenceDrawer({
  detail,
  initialMode,
  busy,
  error,
  onClose,
  onSave,
  onReplace,
  onDownload,
  onArchive,
  onRestore,
}: {
  detail: EvidenceDetail;
  initialMode: EvidenceDrawerMode;
  busy: boolean;
  error: string;
  onClose: () => void;
  onSave: (values: { title: string; evidence_category: EvidenceCategory; context_note: string }) => Promise<void>;
  onReplace: (file: File) => Promise<void>;
  onDownload: () => Promise<void>;
  onArchive: () => void;
  onRestore: () => Promise<void>;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const replacementInput = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState(initialMode);
  const [title, setTitle] = useState(detail.document.title || detail.document.original_filename || "Your work");
  const [category, setCategory] = useState<EvidenceCategory>(evidenceCategory(detail.document));
  const [context, setContext] = useState(detail.document.context_note || "");
  const { document, usage } = detail;
  const archived = Boolean(document.archived_at);
  const updated = document.updated_at || document.processed_at || document.created_at;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
    return () => { if (dialog?.open) dialog.close(); };
  }, []);

  useEffect(() => setMode(initialMode), [initialMode]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    await onSave({ title, evidence_category: category, context_note: context });
    setMode("view");
  }

  return (
    <dialog ref={dialogRef} className="ws-drawer" onCancel={(event) => { event.preventDefault(); onClose(); }}>
      <div className="ws-drawer-shell">
        <header>
          <div><p className="ws-eyebrow">Your work</p><h2 className="display">{document.title || document.original_filename || "Your work"}</h2></div>
          <button type="button" onClick={onClose} aria-label="Close details"><X size={20} /></button>
        </header>

        {usage.active_diagnostic_count ? (
          <div className="ws-callout">
            <strong>This is part of a session in progress.</strong>
            <p>Changes will apply to future sessions. The session in progress keeps the version it already uses.</p>
          </div>
        ) : null}

        {mode === "view" ? (
          <div className="ws-drawer-body">
            <dl className="ws-fact-grid">
              <div><dt>Type</dt><dd>{evidenceCategoryLabel(evidenceCategory(document))}</dd></div>
              <div><dt>Updated</dt><dd>{formatWorkspaceDate(updated)}</dd></div>
              <div><dt>Original file</dt><dd>{document.original_filename || "Text you added"}</dd></div>
              <div><dt>Version</dt><dd>{document.version_number}</dd></div>
            </dl>

            <section className="ws-drawer-section"><h3>Context for Mirror</h3><p className={document.context_note ? "" : "ws-muted-copy"}>{document.context_note || "No additional context has been added."}</p></section>
            <section className="ws-drawer-section"><h3>What Mirror extracted</h3><MirrorUnderstanding detail={detail} /></section>
            <section className="ws-drawer-section">
              <h3>Used in sessions</h3>
              {usage.diagnostics.length ? (
                <div className="ws-usage-list">
                  {usage.diagnostics.map((diagnostic) => (
                    <a key={diagnostic.session_id} href={diagnostic.status === "COMPLETED" ? `/app/report/${diagnostic.session_id}` : `/diagnostics`}>
                      <span><strong>{diagnostic.target_role}</strong><small>{diagnostic.status.toLowerCase().replaceAll("_", " ")}</small></span>
                      <span>Open</span>
                    </a>
                  ))}
                </div>
              ) : <p className="ws-muted-copy">This version hasn't been used in a session yet.</p>}
            </section>
          </div>
        ) : (
          <form className="ws-edit-form" onSubmit={submit}>
            <label><span>Title</span><input className="field" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={160} required autoFocus={mode === "edit"} /></label>
            <label><span>Category</span><select className="field" value={category} onChange={(event) => setCategory(event.target.value as EvidenceCategory)} autoFocus={mode === "category"}>{EVIDENCE_CATEGORIES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
            <label><span>Context for Mirror</span><textarea className="field" value={context} onChange={(event) => setContext(event.target.value)} maxLength={4000} rows={7} autoFocus={mode === "context"} placeholder="Add what you led, how big the work was, when it happened, or what came of it." /><small>{context.length}/4000 · Used only in future sessions.</small></label>
            <div className="ws-form-actions"><button type="button" className="button-secondary" onClick={() => setMode("view")}>Cancel</button><button type="submit" className="button-primary" disabled={busy || !title.trim()}>{busy ? <SpinnerGap className="interview-spinner" size={17} /> : null} Save changes</button></div>
          </form>
        )}

        {error ? <p className="ws-dialog-error" role="alert">{error}</p> : null}

        {mode === "view" ? (
          <footer className="ws-drawer-actions">
            {archived ? (
              <button type="button" onClick={() => void onRestore()} disabled={busy}><ArrowCounterClockwise size={17} /> Restore to library</button>
            ) : (
              <>
                <button type="button" onClick={() => setMode("edit")}><FileText size={17} /> Edit details</button>
                {document.storage_path ? <button type="button" onClick={() => replacementInput.current?.click()} disabled={busy}><Swap size={17} /> Replace file</button> : null}
                {document.storage_path ? <button type="button" onClick={() => void onDownload()} disabled={busy}><DownloadSimple size={17} /> Download</button> : null}
                <button type="button" className="is-destructive" onClick={onArchive}><Trash size={17} /> Remove</button>
              </>
            )}
            <input ref={replacementInput} className="sr-only" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => { const file = event.target.files?.[0]; if (file) void onReplace(file); event.currentTarget.value = ""; }} />
          </footer>
        ) : null}
      </div>
    </dialog>
  );
}
