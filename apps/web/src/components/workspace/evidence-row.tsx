"use client";

import {
  ArrowCounterClockwise,
  Certificate,
  DotsThree,
  DownloadSimple,
  FileText,
  FolderOpen,
  NotePencil,
  PencilSimple,
  Swap,
  Trash,
} from "@phosphor-icons/react";

import { evidenceCategory, evidenceCategoryLabel } from "@/components/workspace/evidence-types";
import { formatWorkspaceDate } from "@/components/workspace/workspace-utils";
import type { EvidenceDetail, MirrorDocument } from "@/lib/api";

function EvidenceIcon({ document }: { document: MirrorDocument }) {
  const category = evidenceCategory(document);
  if (category === "CERTIFICATE") return <Certificate size={20} />;
  if (["PROJECT", "CASE_STUDY", "WORK_SAMPLE", "PORTFOLIO"].includes(category)) return <FolderOpen size={20} />;
  return <FileText size={20} />;
}

function usageLabel(detail: EvidenceDetail) {
  const { usage } = detail;
  if (usage.active_diagnostic_count) {
    return `Used in ${usage.active_diagnostic_count} active ${usage.active_diagnostic_count === 1 ? "diagnostic" : "diagnostics"}`;
  }
  if (usage.completed_diagnostic_count) {
    return `Used in ${usage.completed_diagnostic_count} completed ${usage.completed_diagnostic_count === 1 ? "diagnostic" : "diagnostics"}`;
  }
  return "Available for future diagnostics";
}

/* Status reads from the document's real lifecycle state -- pulse (green) for
   ready/supported, brass for a state that still needs attention, danger for
   archived/error. Never a fabricated progress gauge. */
function statusTone(archived: boolean, status: MirrorDocument["status"]) {
  if (archived) return "archived";
  if (status === "UPLOADED" || status === "PROCESSING") return "active"; // needs reading -> brass
  if (status === "FAILED") return "error";
  return "ready";
}

export type EvidenceRowAction = "open" | "edit" | "replace" | "category" | "context" | "download" | "archive" | "restore";

export function EvidenceRow({
  detail,
  selected,
  onSelect,
  onAction,
}: {
  detail: EvidenceDetail;
  selected: boolean;
  onSelect: (selected: boolean) => void;
  onAction: (action: EvidenceRowAction) => void;
}) {
  const { document } = detail;
  const archived = Boolean(document.archived_at);
  const title = document.title || document.original_filename || evidenceCategoryLabel(evidenceCategory(document));
  const updated = document.updated_at || document.processed_at || document.created_at;
  const tone = statusTone(archived, document.status);

  return (
    <article className={`ws-evidence-row${selected ? " is-selected" : ""}`}>
      <label className="ws-evidence-select">
        <span className="sr-only">Select {title}</span>
        <input type="checkbox" checked={selected} onChange={(event) => onSelect(event.target.checked)} />
      </label>
      <span className="ws-evidence-icon"><EvidenceIcon document={document} /></span>
      <button type="button" className="ws-evidence-main" onClick={() => onAction("open")}>
        <strong>{title}</strong>
        <span>{evidenceCategoryLabel(evidenceCategory(document))} · Version {document.version_number}</span>
      </button>
      <div className="ws-evidence-usage">
        <span className={detail.usage.active_diagnostic_count ? "is-active" : ""}>{usageLabel(detail)}</span>
        <time dateTime={updated}>Updated {formatWorkspaceDate(updated)}</time>
      </div>
      <span className={`ws-status-chip is-${tone}`}>
        <i aria-hidden="true" />
        {archived ? "Removed" : document.status === "UPLOADED" ? "Needs reading" : document.status.toLowerCase()}
      </span>
      <details className="ws-evidence-menu">
        <summary aria-label={`Actions for ${title}`}><DotsThree size={22} weight="bold" /></summary>
        <div>
          <button type="button" onClick={() => onAction("open")}><FileText size={16} /> Open</button>
          {archived ? (
            <button type="button" onClick={() => onAction("restore")}><ArrowCounterClockwise size={16} /> Restore</button>
          ) : (
            <>
              <button type="button" onClick={() => onAction("edit")}><PencilSimple size={16} /> Edit details</button>
              {document.storage_path ? <button type="button" onClick={() => onAction("replace")}><Swap size={16} /> Replace file</button> : null}
              <button type="button" onClick={() => onAction("category")}><FolderOpen size={16} /> Change category</button>
              <button type="button" onClick={() => onAction("context")}><NotePencil size={16} /> {document.context_note ? "Edit context" : "Add context"}</button>
              {document.storage_path ? <button type="button" onClick={() => onAction("download")}><DownloadSimple size={16} /> Download original</button> : null}
              <button type="button" className="is-destructive" onClick={() => onAction("archive")}><Trash size={16} /> Remove from library</button>
            </>
          )}
        </div>
      </details>
    </article>
  );
}
