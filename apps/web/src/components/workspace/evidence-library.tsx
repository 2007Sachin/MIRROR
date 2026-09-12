"use client";

import {
  ArrowCounterClockwise,
  CaretDown,
  MagnifyingGlass,
  Plus,
  Trash,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { EvidenceDrawer, type EvidenceDrawerMode } from "@/components/workspace/evidence-drawer";
import { EvidenceRemoveDialog, EvidenceUploadDialog } from "@/components/workspace/evidence-dialogs";
import { EvidenceRow, type EvidenceRowAction } from "@/components/workspace/evidence-row";
import { EVIDENCE_CATEGORIES, evidenceCategory } from "@/components/workspace/evidence-types";
import { AppShell } from "@/components/workspace/app-shell";
import {
  ApiError,
  downloadEvidenceDocument,
  mirrorApi,
  uploadEvidenceDocument,
  type EvidenceCategory,
  type EvidenceDetail,
  type Profile,
} from "@/lib/api";

type EvidenceFilter = "ALL" | EvidenceCategory;
type EvidenceSort = "UPDATED" | "ADDED" | "NAME";
type LibraryView = "CURRENT" | "REMOVED";

function replaceDetails(items: EvidenceDetail[], next: EvidenceDetail) {
  return items.map((item) => item.document.id === next.document.id ? next : item);
}

export function EvidenceLibrary() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [items, setItems] = useState<EvidenceDetail[]>([]);
  const [view, setView] = useState<LibraryView>("CURRENT");
  const [filter, setFilter] = useState<EvidenceFilter>("ALL");
  const [sort, setSort] = useState<EvidenceSort>("UPDATED");
  const [search, setSearch] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [drawer, setDrawer] = useState<{ detail: EvidenceDetail; mode: EvidenceDrawerMode } | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [replacing, setReplacing] = useState<EvidenceDetail | null>(null);
  const [removing, setRemoving] = useState<EvidenceDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState("");
  const [dialogError, setDialogError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    setError("");
    try {
      const [nextItems, nextProfile] = await Promise.all([mirrorApi.evidence(true), mirrorApi.me()]);
      setItems(nextItems);
      setProfile(nextProfile);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) {
        router.replace("/login?reason=session_expired");
        return;
      }
      setError("Mirror could not load your professional evidence. Your saved files have not been changed.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const visible = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return items
      .filter((item) => view === "REMOVED" ? Boolean(item.document.archived_at) : !item.document.archived_at)
      .filter((item) => filter === "ALL" || evidenceCategory(item.document) === filter)
      .filter((item) => {
        if (!query) return true;
        return [item.document.title, item.document.original_filename, item.document.context_note]
          .some((value) => value?.toLocaleLowerCase().includes(query));
      })
      .sort((left, right) => {
        if (sort === "NAME") return (left.document.title || "").localeCompare(right.document.title || "");
        const leftDate = sort === "ADDED" ? left.document.created_at : left.document.updated_at || left.document.created_at;
        const rightDate = sort === "ADDED" ? right.document.created_at : right.document.updated_at || right.document.created_at;
        return new Date(rightDate).getTime() - new Date(leftDate).getTime();
      });
  }, [filter, items, search, sort, view]);

  const selected = items.filter((item) => selectedIds.has(item.document.id));
  const currentCount = items.filter((item) => !item.document.archived_at).length;
  const removedCount = items.length - currentCount;
  const usedCount = items.filter((item) => !item.document.archived_at && item.usage.diagnostics.length).length;

  function select(id: string, checked: boolean) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (checked) next.add(id); else next.delete(id);
      return next;
    });
  }

  async function upload(
    file: File,
    values: { title: string; evidence_category: EvidenceCategory; context_note: string },
  ) {
    setBusy(true);
    setUploadProgress(0);
    setDialogError("");
    try {
      const result = await uploadEvidenceDocument(file, values, setUploadProgress);
      let readingIncomplete = false;
      if (result.document.document_type === "RESUME") {
        try {
          await mirrorApi.analyzeResume(result.document.id);
        } catch {
          readingIncomplete = true;
        }
      }
      await load();
      setShowUpload(false);
      setNotice(readingIncomplete
        ? "Evidence added, but Mirror could not finish reading this resume. The file is safe; try again later."
        : "Evidence added. Mirror will use this version in future diagnostics.");
    } catch (reason) {
      setDialogError(reason instanceof ApiError ? reason.message : "We couldn't add this evidence. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function replace(
    file: File,
    values?: { title: string; evidence_category: EvidenceCategory; context_note: string },
  ) {
    const target = replacing || drawer?.detail;
    if (!target) return;
    const metadata = values ?? {
      title: target.document.title || target.document.original_filename || "Professional evidence",
      evidence_category: evidenceCategory(target.document),
      context_note: target.document.context_note || "",
    };
    setBusy(true);
    setUploadProgress(0);
    setDialogError("");
    try {
      const result = await uploadEvidenceDocument(
        file,
        { ...metadata, acknowledge_active_use: Boolean(target.usage.active_diagnostic_count) },
        setUploadProgress,
        target.document.id,
      );
      let readingIncomplete = false;
      if (result.document.document_type === "RESUME") {
        try {
          await mirrorApi.analyzeResume(result.document.id);
        } catch {
          readingIncomplete = true;
        }
      }
      await load();
      setReplacing(null);
      setDrawer(null);
      setNotice(readingIncomplete
        ? "File replaced, but Mirror could not finish reading this resume. Historical diagnostics remain unchanged."
        : "File replaced. Diagnostics already completed still use the previous version.");
    } catch (reason) {
      setDialogError(reason instanceof ApiError ? reason.message : "We couldn't replace this evidence. Your original file is unchanged.");
    } finally {
      setBusy(false);
    }
  }

  async function save(values: { title: string; evidence_category: EvidenceCategory; context_note: string }) {
    if (!drawer) return;
    setBusy(true);
    setDialogError("");
    try {
      const next = await mirrorApi.updateEvidence(drawer.detail.document.id, {
        ...values,
        context_note: values.context_note.trim() || null,
        acknowledge_active_use: Boolean(drawer.detail.usage.active_diagnostic_count),
      });
      await load();
      setDrawer({ detail: next, mode: "view" });
      setNotice("Evidence details updated for future diagnostics.");
    } catch (reason) {
      setDialogError(reason instanceof ApiError ? reason.message : "We couldn't update this evidence.");
    } finally {
      setBusy(false);
    }
  }

  async function archive() {
    if (!removing.length) return;
    setBusy(true);
    setDialogError("");
    try {
      await Promise.all(removing.map((item) => mirrorApi.archiveEvidence(item.document.id, Boolean(item.usage.active_diagnostic_count))));
      await load();
      setSelectedIds(new Set());
      setRemoving([]);
      setNotice("Evidence removed from future diagnostics. Historical references were preserved.");
    } catch (reason) {
      setDialogError(reason instanceof ApiError ? reason.message : "We couldn't remove this evidence. It remains in your library.");
    } finally {
      setBusy(false);
    }
  }

  async function restore(detail: EvidenceDetail) {
    setBusy(true);
    setDialogError("");
    try {
      const next = await mirrorApi.restoreEvidence(detail.document.id);
      setItems((current) => replaceDetails(current, next));
      setDrawer(null);
      setNotice("Evidence restored and available for future diagnostics.");
    } catch (reason) {
      setDialogError(reason instanceof ApiError ? reason.message : "We couldn't restore this evidence.");
    } finally {
      setBusy(false);
    }
  }

  async function download(detail: EvidenceDetail) {
    setDialogError("");
    try {
      const { blob, filename } = await downloadEvidenceDocument(detail.document.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setDialogError(reason instanceof ApiError ? reason.message : "Mirror could not download the original file.");
    }
  }

  async function bulkCategory(category: EvidenceCategory) {
    if (!selected.length) return;
    setBusy(true);
    setError("");
    try {
      await Promise.all(selected.map((item) => mirrorApi.updateEvidence(item.document.id, {
        evidence_category: category,
        acknowledge_active_use: Boolean(item.usage.active_diagnostic_count),
      })));
      await load();
      setSelectedIds(new Set());
      setNotice("Category updated for the selected evidence.");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Mirror could not update the selected evidence.");
    } finally {
      setBusy(false);
    }
  }

  async function restoreSelected() {
    if (!selected.length) return;
    setBusy(true);
    setError("");
    try {
      await Promise.all(selected.map((item) => mirrorApi.restoreEvidence(item.document.id)));
      await load();
      setSelectedIds(new Set());
      setNotice("Selected evidence restored for future diagnostics.");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Mirror could not restore the selected evidence.");
    } finally {
      setBusy(false);
    }
  }

  function action(detail: EvidenceDetail, nextAction: EvidenceRowAction) {
    setDialogError("");
    if (nextAction === "open") setDrawer({ detail, mode: "view" });
    if (nextAction === "edit") setDrawer({ detail, mode: "edit" });
    if (nextAction === "category") setDrawer({ detail, mode: "category" });
    if (nextAction === "context") setDrawer({ detail, mode: "context" });
    if (nextAction === "replace") setReplacing(detail);
    if (nextAction === "download") void download(detail);
    if (nextAction === "archive") setRemoving([detail]);
    if (nextAction === "restore") void restore(detail);
  }

  return (
    <AppShell profile={profile}>
      <header className="workspace-route-header evidence-library-header">
        <div><p className="app-kicker">Evidence library</p><h1 className="display">Your professional evidence</h1><p>The evidence Mirror is allowed to reason from—managed by you.</p></div>
        <button className="app-primary-button" type="button" onClick={() => { setDialogError(""); setShowUpload(true); }}><Plus size={17} /> Add evidence</button>
      </header>

      <div className="evidence-library-summary" aria-label="Evidence library summary">
        <span><strong>{currentCount}</strong> in your library</span><i /><span><strong>{usedCount}</strong> used in diagnostics</span><i /><span>Archived versions remain attached to historical findings</span>
      </div>

      <div className="evidence-view-tabs" role="tablist" aria-label="Evidence state">
        <button type="button" role="tab" aria-selected={view === "CURRENT"} onClick={() => { setView("CURRENT"); setSelectedIds(new Set()); }}>Current evidence <span>{currentCount}</span></button>
        <button type="button" role="tab" aria-selected={view === "REMOVED"} onClick={() => { setView("REMOVED"); setSelectedIds(new Set()); }}>Recently removed <span>{removedCount}</span></button>
      </div>

      <section className="evidence-toolbar" aria-label="Evidence tools">
        <label className="evidence-search"><MagnifyingGlass size={17} /><span className="sr-only">Search evidence</span><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search evidence" />{search ? <button type="button" onClick={() => setSearch("")} aria-label="Clear search"><X size={15} /></button> : null}</label>
        <label><span className="sr-only">Filter by category</span><select value={filter} onChange={(event) => setFilter(event.target.value as EvidenceFilter)}><option value="ALL">All categories</option>{EVIDENCE_CATEGORIES.map((option) => <option key={option.value} value={option.value}>{option.plural}</option>)}</select><CaretDown size={14} /></label>
        <label><span className="sr-only">Sort evidence</span><select value={sort} onChange={(event) => setSort(event.target.value as EvidenceSort)}><option value="UPDATED">Recently updated</option><option value="ADDED">Recently added</option><option value="NAME">Name</option></select><CaretDown size={14} /></label>
      </section>

      {selected.length ? (
        <div className="evidence-bulk-bar" role="toolbar" aria-label="Bulk evidence actions">
          <strong>{selected.length} selected</strong>
          {view === "CURRENT" ? <><label>Change category <select defaultValue="" onChange={(event) => { if (event.target.value) void bulkCategory(event.target.value as EvidenceCategory); event.target.value = ""; }} disabled={busy}><option value="" disabled>Choose…</option>{EVIDENCE_CATEGORIES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label><button type="button" onClick={() => setRemoving(selected)} disabled={busy}><Trash size={16} /> Remove from library</button></> : <button type="button" onClick={() => void restoreSelected()} disabled={busy}><ArrowCounterClockwise size={16} /> Restore selected</button>}
          <button type="button" className="evidence-bulk-clear" onClick={() => setSelectedIds(new Set())}>Clear</button>
        </div>
      ) : null}

      {notice ? <div className="evidence-notice" role="status"><span>{notice}</span><button type="button" onClick={() => setNotice("")} aria-label="Dismiss"><X size={15} /></button></div> : null}
      {error ? <div className="app-inline-alert" role="alert"><WarningCircle size={18} /><span>{error}</span><button type="button" onClick={() => void load()}>Retry</button></div> : null}

      <section className="evidence-workspace-list app-panel" aria-live="polite">
        {loading ? <div className="workspace-list-skeleton"><i /><i /><i /></div> : null}
        {!loading && !visible.length ? (
          <div className="workspace-route-empty">
            <h2>{view === "REMOVED" ? "Nothing has been removed." : search || filter !== "ALL" ? "No evidence matches this view." : "Your evidence library is empty."}</h2>
            <p>{view === "REMOVED" ? "Evidence removed from future diagnostics will appear here and can be restored." : "Add the documents, projects and achievements Mirror should use when evaluating your experience."}</p>
            {view === "CURRENT" && !search && filter === "ALL" ? <button type="button" onClick={() => setShowUpload(true)}>Add evidence</button> : null}
          </div>
        ) : null}
        {visible.map((detail) => <EvidenceRow key={detail.document.id} detail={detail} selected={selectedIds.has(detail.document.id)} onSelect={(checked) => select(detail.document.id, checked)} onAction={(nextAction) => action(detail, nextAction)} />)}
      </section>

      {drawer ? <EvidenceDrawer detail={drawer.detail} initialMode={drawer.mode} busy={busy} error={dialogError} onClose={() => { setDrawer(null); setDialogError(""); }} onSave={save} onReplace={(file) => replace(file)} onDownload={() => download(drawer.detail)} onArchive={() => { setDrawer(null); setRemoving([drawer.detail]); }} onRestore={() => restore(drawer.detail)} /> : null}
      {showUpload ? <EvidenceUploadDialog busy={busy} progress={uploadProgress} error={dialogError} onClose={() => { if (!busy) { setShowUpload(false); setDialogError(""); } }} onSubmit={upload} /> : null}
      {replacing ? <EvidenceUploadDialog replacing={replacing} busy={busy} progress={uploadProgress} error={dialogError} onClose={() => { if (!busy) { setReplacing(null); setDialogError(""); } }} onSubmit={(file, values) => replace(file, values)} /> : null}
      {removing.length ? <EvidenceRemoveDialog items={removing} busy={busy} error={dialogError} onClose={() => { if (!busy) { setRemoving([]); setDialogError(""); } }} onConfirm={archive} /> : null}
    </AppShell>
  );
}
