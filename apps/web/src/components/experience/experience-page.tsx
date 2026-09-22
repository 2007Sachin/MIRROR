"use client";

import { Plus } from "@phosphor-icons/react";
import { useMemo, useState } from "react";

import { EvidenceDrawer, type EvidenceDrawerMode } from "@/components/workspace/evidence-drawer";
import { EvidenceRemoveDialog, EvidenceUploadDialog } from "@/components/workspace/evidence-dialogs";
import { evidenceCategory } from "@/components/workspace/evidence-types";
import {
  EmptyState,
  PageAlert,
  PageHeader,
  PageLoading,
  PageShell,
  Section,
  usePageData,
} from "@/components/workspace/page-shell";
import {
  ApiError,
  downloadEvidenceDocument,
  mirrorApi,
  uploadEvidenceDocument,
  type EvidenceCategory,
  type EvidenceDetail,
  type ResumeAnalysis,
} from "@/lib/api";
import { experience as t } from "@/lib/copy";
import { formatShortDay } from "@/lib/dashboard-view";
import {
  experienceGuidance,
  experienceState,
  groupExperience,
  newestFirst,
  readAchievements,
  type ResumeOutput,
} from "@/lib/experience-view";

type ExperienceData = { items: EvidenceDetail[]; resume: ResumeAnalysis | null };

async function loadExperience(): Promise<ExperienceData> {
  const items = await mirrorApi.evidence(true);
  const newestResume = newestFirst(
    items.filter((item) => !item.document.archived_at && evidenceCategory(item.document) === "RESUME"),
  )[0];
  if (!newestResume) return { items, resume: null };
  // A resume that has never been read is not an error: the page says so instead.
  const resume = await mirrorApi.resumeAnalysis(newestResume.document.id).catch(() => null);
  return { items, resume };
}

export function ExperiencePage() {
  const { state, data, error, reload } = usePageData(loadExperience, t.errors.load);
  const [drawer, setDrawer] = useState<{ detail: EvidenceDetail; mode: EvidenceDrawerMode } | null>(null);
  const [adding, setAdding] = useState<EvidenceCategory | null>(null);
  const [replacing, setReplacing] = useState<EvidenceDetail | null>(null);
  const [removing, setRemoving] = useState<EvidenceDetail[]>([]);
  const [busy, setBusy] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dialogError, setDialogError] = useState("");

  const groups = useMemo(() => groupExperience(data?.items ?? []), [data]);
  const output: ResumeOutput | null = data?.resume?.status === "COMPLETED" ? data.resume.output : null;
  const pageState = experienceState(groups, data?.resume ?? null);
  const guidance = experienceGuidance(groups, output, pageState);
  const achievements = useMemo(() => readAchievements(output), [output]);
  const resume = newestFirst(groups.resumes)[0] ?? null;
  const removed = useMemo(
    () => newestFirst((data?.items ?? []).filter((item) => Boolean(item.document.archived_at))),
    [data],
  );

  async function upload(file: File, values: { title: string; evidence_category: EvidenceCategory; context_note: string }) {
    setBusy(true);
    setUploadProgress(0);
    setDialogError("");
    try {
      const result = await uploadEvidenceDocument(file, values, setUploadProgress);
      if (result.document.document_type === "RESUME") {
        await mirrorApi.analyzeResume(result.document.id).catch(() => null);
      }
      await reload();
      setAdding(null);
    } catch (reason) {
      setDialogError(reason instanceof ApiError ? reason.message : t.errors.load);
    } finally {
      setBusy(false);
    }
  }

  async function replace(file: File, values?: { title: string; evidence_category: EvidenceCategory; context_note: string }) {
    const target = replacing ?? drawer?.detail;
    if (!target) return;
    const metadata = values ?? {
      title: target.document.title || target.document.original_filename || "Your work",
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
      if (result.document.document_type === "RESUME") {
        await mirrorApi.analyzeResume(result.document.id).catch(() => null);
      }
      await reload();
      setReplacing(null);
      setDrawer(null);
    } catch (reason) {
      setDialogError(reason instanceof ApiError ? reason.message : t.errors.load);
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
      await reload();
      setDrawer({ detail: next, mode: "view" });
    } catch (reason) {
      setDialogError(reason instanceof ApiError ? reason.message : t.errors.load);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!removing.length) return;
    setBusy(true);
    setDialogError("");
    try {
      await Promise.all(
        removing.map((item) => mirrorApi.archiveEvidence(item.document.id, Boolean(item.usage.active_diagnostic_count))),
      );
      await reload();
      setRemoving([]);
    } catch (reason) {
      setDialogError(reason instanceof ApiError ? reason.message : t.errors.load);
    } finally {
      setBusy(false);
    }
  }

  async function restore(detail: EvidenceDetail) {
    setBusy(true);
    setDialogError("");
    try {
      await mirrorApi.restoreEvidence(detail.document.id);
      await reload();
      setDrawer(null);
    } catch (reason) {
      setDialogError(reason instanceof ApiError ? reason.message : t.errors.load);
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
      setDialogError(reason instanceof ApiError ? reason.message : t.errors.load);
    }
  }

  const empty = pageState === "EMPTY";

  return (
    <PageShell>
      <PageHeader
        eyebrow={t.eyebrow}
        title={t.title}
        intro={t.intro}
        action={
          <button className="dh-primary-action" type="button" onClick={() => { setDialogError(""); setAdding("OTHER"); }}>
            <Plus size={16} aria-hidden="true" /> {t.add}
          </button>
        }
      />

      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}

      {state === "ready" && empty ? (
        <EmptyState title={t.empty.title} body={t.empty.body}>
          <button className="dh-primary-action" type="button" onClick={() => { setDialogError(""); setAdding("RESUME"); }}>
            <Plus size={16} aria-hidden="true" /> {t.empty.action}
          </button>
        </EmptyState>
      ) : null}

      {state === "ready" && !empty ? (
        <div className="dh-home-sections">
          {guidance ? <p className="dh-guidance">{guidance}</p> : null}

          <Section id="experience-resume" label={t.sections.resume} title={t.sections.resume}>
            {resume ? (
              <ul className="dh-row-list">
                <li>
                  <span className="dh-row-main">
                    <strong>{resume.document.title || resume.document.original_filename || t.sections.resume}</strong>
                    <small>{`Added ${formatShortDay(resume.document.updated_at || resume.document.created_at)}`}</small>
                  </span>
                  <span className="dh-row-actions">
                    <button type="button" className="dh-text-action" onClick={() => setDrawer({ detail: resume, mode: "view" })}>
                      {t.view}
                    </button>
                    <button type="button" className="dh-text-action" onClick={() => { setDialogError(""); setReplacing(resume); }}>
                      {t.replace}
                    </button>
                  </span>
                </li>
              </ul>
            ) : (
              <p className="dh-review-empty">{t.addResume}</p>
            )}
          </Section>

          <Section id="experience-work" label={t.sections.work} title={t.sections.work} body={t.fromResume}>
            {output?.work_experience.length ? (
              <ul className="dh-row-list">
                {output.work_experience.map((entry, index) => (
                  <li key={`${entry.organization}-${entry.role}-${index}`}>
                    <span className="dh-row-main">
                      <strong>{entry.organization}</strong>
                      <small>{entry.role}</small>
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="dh-review-empty">{t.emptyWork}</p>
            )}
            <p className="dh-fine-print">{t.fromResumeNote}</p>
          </Section>

          <Section
            id="experience-projects"
            label={t.sections.projects}
            title={t.sections.projects}
            action={
              <button className="dh-text-action" type="button" onClick={() => { setDialogError(""); setAdding("PROJECT"); }}>
                <Plus size={15} aria-hidden="true" /> {t.addProjectAction}
              </button>
            }
          >
            {output?.projects.length || groups.projects.length ? (
              <ul className="dh-row-list">
                {output?.projects.map((project, index) => (
                  <li key={`${project.project_name}-${index}`}>
                    <span className="dh-row-main">
                      <strong>{project.project_name}</strong>
                      <small>{t.fromResume}</small>
                    </span>
                  </li>
                ))}
                {newestFirst(groups.projects).map((item) => (
                  <ExperienceRow
                    key={item.document.id}
                    detail={item}
                    onOpen={() => setDrawer({ detail: item, mode: "view" })}
                    onRemove={() => { setDialogError(""); setRemoving([item]); }}
                  />
                ))}
              </ul>
            ) : (
              <p className="dh-review-empty">{t.emptyProjects}</p>
            )}
          </Section>

          <Section
            id="experience-achievements"
            label={t.sections.achievements}
            title={t.sections.achievements}
            action={
              <button className="dh-text-action" type="button" onClick={() => { setDialogError(""); setAdding("ACHIEVEMENT"); }}>
                <Plus size={15} aria-hidden="true" /> {t.addAchievementAction}
              </button>
            }
          >
            {achievements.length || groups.achievements.length ? (
              <ul className="dh-row-list">
                {achievements.map((entry, index) => (
                  <li key={`${entry.title}-${index}`}>
                    <span className="dh-row-main">
                      <strong>{entry.title}</strong>
                      <small>{entry.detail || t.fromResume}</small>
                    </span>
                  </li>
                ))}
                {newestFirst(groups.achievements).map((item) => (
                  <ExperienceRow
                    key={item.document.id}
                    detail={item}
                    onOpen={() => setDrawer({ detail: item, mode: "view" })}
                    onRemove={() => { setDialogError(""); setRemoving([item]); }}
                  />
                ))}
              </ul>
            ) : (
              <p className="dh-review-empty">{t.emptyAchievements}</p>
            )}
          </Section>

          {removed.length ? (
            <Section id="experience-removed" label={t.removed} title={t.removed} body={t.removedBody}>
              <ul className="dh-row-list">
                {removed.map((item) => (
                  <li key={item.document.id}>
                    <span className="dh-row-main">
                      <strong>{item.document.title || item.document.original_filename || t.sections.other}</strong>
                      <small>{formatShortDay(item.document.archived_at)}</small>
                    </span>
                    <span className="dh-row-actions">
                      <button type="button" className="dh-text-action" onClick={() => void restore(item)} disabled={busy}>
                        {t.restore}
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
            </Section>
          ) : null}

          {groups.other.length ? (
            <Section id="experience-other" label={t.sections.other} title={t.sections.other}>
              <ul className="dh-row-list">
                {newestFirst(groups.other).map((item) => (
                  <ExperienceRow
                    key={item.document.id}
                    detail={item}
                    onOpen={() => setDrawer({ detail: item, mode: "view" })}
                    onRemove={() => { setDialogError(""); setRemoving([item]); }}
                  />
                ))}
              </ul>
            </Section>
          ) : null}
        </div>
      ) : null}

      {drawer ? (
        <EvidenceDrawer
          detail={drawer.detail}
          initialMode={drawer.mode}
          busy={busy}
          error={dialogError}
          onClose={() => { setDrawer(null); setDialogError(""); }}
          onSave={save}
          onReplace={(file) => replace(file)}
          onDownload={() => download(drawer.detail)}
          onArchive={() => { setDrawer(null); setRemoving([drawer.detail]); }}
          onRestore={() => restore(drawer.detail)}
        />
      ) : null}
      {adding ? (
        <EvidenceUploadDialog
          initialCategory={adding}
          busy={busy}
          progress={uploadProgress}
          error={dialogError}
          onClose={() => { if (!busy) { setAdding(null); setDialogError(""); } }}
          onSubmit={upload}
        />
      ) : null}
      {replacing ? (
        <EvidenceUploadDialog
          replacing={replacing}
          busy={busy}
          progress={uploadProgress}
          error={dialogError}
          onClose={() => { if (!busy) { setReplacing(null); setDialogError(""); } }}
          onSubmit={(file, values) => replace(file, values)}
        />
      ) : null}
      {removing.length ? (
        <EvidenceRemoveDialog
          items={removing}
          busy={busy}
          error={dialogError}
          onClose={() => { if (!busy) { setRemoving([]); setDialogError(""); } }}
          onConfirm={remove}
        />
      ) : null}
    </PageShell>
  );
}

function ExperienceRow({
  detail,
  onOpen,
  onRemove,
}: {
  detail: EvidenceDetail;
  onOpen: () => void;
  onRemove: () => void;
}) {
  return (
    <li>
      <span className="dh-row-main">
        <strong>{detail.document.title || detail.document.original_filename || t.sections.other}</strong>
        <small>{formatShortDay(detail.document.updated_at || detail.document.created_at)}</small>
      </span>
      <span className="dh-row-actions">
        <button type="button" className="dh-text-action" onClick={onOpen}>
          {t.viewDetails}
        </button>
        <button type="button" className="dh-text-action is-quiet" onClick={onRemove}>
          {t.remove}
        </button>
      </span>
    </li>
  );
}
