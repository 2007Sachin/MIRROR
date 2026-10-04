"use client";

import { ArrowRight, Check, FileText, UploadSimple } from "@phosphor-icons/react";
import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";

import { StepHeading, type Report } from "@/components/onboarding/shared";
import { TargetFields, looksLikeSde, targetBody, type TargetChoice } from "@/components/onboarding/target-fields";
import { mirrorApi, uploadRoleBriefDocument, type MirrorDocument, type RoleAnalysis } from "@/lib/api";
import { createTarget, targetsAvailable } from "@/lib/api-targets";
import { onboardingCopy } from "@/lib/copy-onboarding";
import { describeFileRejection, friendlyAnalysisError, friendlyDocumentError } from "@/lib/documents";

const t = onboardingCopy.role;
type BriefMode = "upload" | "paste" | "none" | null;

export type RoleSetup = { role: RoleAnalysis; company: string; brief: MirrorDocument | null; skipped: boolean };

export function RoleStep({
  initialRole = "",
  initialCompany = "",
  initialBrief = null,
  initialSkipped = false,
  reuse = null,
  eyebrow,
  withCompany = true,
  report,
  onReady,
}: {
  initialRole?: string;
  initialCompany?: string;
  initialBrief?: MirrorDocument | null;
  initialSkipped?: boolean;
  /** A role profile already set up here; reused when the role name is unchanged. */
  reuse?: RoleAnalysis | null;
  eyebrow?: string;
  /** Only the first role keeps an organisation; other roles have nowhere to save one yet. */
  withCompany?: boolean;
  report: Report;
  onReady: (setup: RoleSetup) => Promise<void>;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [role, setRole] = useState(initialRole);
  const [company, setCompany] = useState(initialCompany);
  const [brief, setBrief] = useState<MirrorDocument | null>(initialBrief);
  const [mode, setMode] = useState<BriefMode>(initialBrief ? (initialBrief.original_filename ? "upload" : "paste") : initialSkipped ? "none" : null);
  const [pasted, setPasted] = useState(initialBrief?.original_filename ? "" : initialBrief?.raw_text ?? "");
  const [progress, setProgress] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  // Replacement controls stay locked while an upload or the role setup runs.
  const locked = busy || progress !== null;
  // Optional interview target (company, SDE family, level, country): only offered when targets are available.
  const [targetsOn, setTargetsOn] = useState(false);
  const [targetOpen, setTargetOpen] = useState(false);
  const [familyTouched, setFamilyTouched] = useState(false);
  const [target, setTarget] = useState<Omit<TargetChoice, "company">>({ family: false, level: "not_sure", country: "not_sure" });
  const sde = looksLikeSde(role);
  const family = familyTouched ? target.family : sde;

  useEffect(() => {
    let active = true;
    void targetsAvailable().then((on) => { if (active) setTargetsOn(on); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (targetsOn && sde) setTargetOpen(true);
  }, [targetsOn, sde]);

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const rejection = describeFileRejection(file, "role brief");
    if (rejection) return report(rejection);
    report("");
    setProgress(0);
    try {
      const document = await uploadRoleBriefDocument(file, setProgress);
      setBrief(document);
      setMode("upload");
    } catch (reason) {
      report(friendlyDocumentError(reason, "role brief"), reason);
    } finally {
      setProgress(null);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanRole = role.trim();
    if (cleanRole.length < 2) return;
    if (!mode) return report(t.chooseBrief);
    report("");
    setBusy(true);
    try {
      let chosen = mode === "none" ? null : brief;
      if (mode === "paste") {
        const text = pasted.trim();
        if (!text) return report(t.pasteEmpty);
        if (!chosen || chosen.original_filename || chosen.raw_text !== text) chosen = await mirrorApi.createJobDescription(text);
      }
      if (mode === "upload" && !chosen) return report(t.chooseBrief);
      const reuseId = reuse?.target_role.trim().toLocaleLowerCase() === cleanRole.toLocaleLowerCase() ? reuse.id : undefined;
      const analysed = await mirrorApi.analyzeRole({
        target_role: cleanRole,
        ...(chosen ? { job_description_document_id: chosen.id } : {}),
        ...(reuseId ? { role_profile_id: reuseId } : {}),
      });
      if (analysed.latest_analysis?.status !== "COMPLETED") return report(t.roleNotReady);
      const body = targetsOn ? targetBody(analysed.id, { ...target, family, company }) : null;
      // The target is optional: an existing one, or targets being unavailable, never blocks the role.
      if (body) await createTarget(body).catch(() => null);
      await onReady({ role: analysed, company: company.trim(), brief: chosen, skipped: mode === "none" });
    } catch (reason) {
      report(friendlyAnalysisError(reason, "role"), reason);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="ob-step" aria-busy={busy}>
      <StepHeading eyebrow={eyebrow} title={t.title} intro={t.intro} />
      <div className={withCompany && !targetsOn ? "ob-fields ob-two-col" : "ob-fields"}>
        <label>
          <span>{t.roleLabel}</span>
          <input className="field" value={role} onChange={(event) => setRole(event.target.value)} minLength={2} maxLength={160} required disabled={busy} placeholder={t.rolePlaceholder} />
        </label>
        {withCompany && !targetsOn && <label>
          <span>{t.orgLabel} <small>{t.optional}</small></span>
          <input className="field" value={company} onChange={(event) => setCompany(event.target.value)} maxLength={160} disabled={busy} placeholder={t.orgPlaceholder} />
        </label>}
      </div>
      {targetsOn && (
        <TargetFields
          value={{ ...target, family, company }}
          onChange={(next) => {
            if (next.family !== family) setFamilyTouched(true);
            setCompany(next.company);
            setTarget({ family: next.family, level: next.level, country: next.country });
          }}
          open={targetOpen}
          onToggle={setTargetOpen}
          disabled={busy}
        />
      )}
      <fieldset className="op-brief" disabled={locked}>
        <legend>{t.briefTitle}</legend>
        <p className="op-muted">{t.briefIntro}</p>
        <div className="op-choice-row">
          <button type="button" className="op-choice" aria-pressed={mode === "upload"} onClick={() => fileInput.current?.click()}>
            <UploadSimple size={18} aria-hidden="true" /> {t.upload}
          </button>
          <button type="button" className="op-choice" aria-pressed={mode === "paste"} onClick={() => setMode("paste")}>
            <FileText size={18} aria-hidden="true" /> {t.paste}
          </button>
          <button type="button" className="op-choice" aria-pressed={mode === "none"} onClick={() => setMode("none")}>
            {t.skip}
          </button>
        </div>
        <input ref={fileInput} className="sr-only" type="file" tabIndex={-1} aria-hidden="true" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={upload} />
        {mode === "paste" && (
          <label className="op-paste">
            <span>{t.pasteLabel}</span>
            <textarea className="field" value={pasted} onChange={(event) => setPasted(event.target.value)} maxLength={100000} placeholder={t.pastePlaceholder} />
          </label>
        )}
        {mode === "upload" && brief?.original_filename && (
          <p className="op-confirm"><Check size={16} aria-hidden="true" /> {t.uploaded}: {brief.original_filename}</p>
        )}
        {progress !== null && (
          <>
            <p role="status" aria-live="polite" className="op-muted">{t.uploading(progress)}</p>
            <div className="ob-upload-progress" role="progressbar" aria-label={t.uploadProgress} aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}>
              <span style={{ width: `${progress}%` }} />
            </div>
          </>
        )}
      </fieldset>
      {busy && <p role="status" aria-live="polite" className="op-muted">{t.workingNote}</p>}
      <div className="ob-actions">
        <span />
        <button className="button-primary op-target" disabled={locked || role.trim().length < 2 || !mode}>
          {busy ? t.working : t.continue} <ArrowRight size={18} aria-hidden="true" />
        </button>
      </div>
    </form>
  );
}
