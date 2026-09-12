import { ArrowRight, File, FileText, FolderOpen } from "@phosphor-icons/react";
import Link from "next/link";

import type { MirrorDocument } from "@/lib/api";
import { displayDocumentName, documentLabel, formatWorkspaceDate } from "@/components/workspace/workspace-utils";

function DocumentIcon({ type }: { type: MirrorDocument["document_type"] }) {
  if (type === "RESUME") return <FileText size={20} />;
  if (type === "PROJECT") return <FolderOpen size={20} />;
  return <File size={20} />;
}
export function EvidencePreview({ documents, unavailable = false }: { documents: MirrorDocument[]; unavailable?: boolean }) {
  return (
    <section className="dashboard-evidence-preview app-panel" aria-labelledby="evidence-preview-title">
      <div className="app-section-heading is-split">
        <div>
          <h2 id="evidence-preview-title">Your evidence library</h2>
          <p>The context Mirror can use in a diagnostic.</p>
        </div>
        <Link href="/evidence">View all <ArrowRight size={14} /></Link>
      </div>
      {unavailable ? (
        <p className="app-empty-copy">Your evidence library is temporarily unavailable.</p>
      ) : documents.length ? (
        <div className="evidence-preview-grid">
          {documents.slice(0, 4).map((document) => (
            <article key={document.id}>
              <span><DocumentIcon type={document.document_type} /></span>
              <strong title={displayDocumentName(document)}>{displayDocumentName(document)}</strong>
              <p>{documentLabel(document)} · {formatWorkspaceDate(document.processed_at || document.created_at)}</p>
            </article>
          ))}
        </div>
      ) : (
        <div className="app-empty-copy">
          <p>No professional evidence has been added yet.</p>
          <Link href="/evidence">Add evidence <ArrowRight size={14} /></Link>
        </div>
      )}
    </section>
  );
}
