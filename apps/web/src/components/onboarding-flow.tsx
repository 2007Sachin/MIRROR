"use client";

import "@/styles/onboarding.css";
import "@/styles/onboarding-plan.css";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ExperienceStep } from "@/components/onboarding/experience-step";
import { PlanReadyStep } from "@/components/onboarding/plan-ready-step";
import { ReviewStep } from "@/components/onboarding/review-step";
import { RoleStep, type RoleSetup } from "@/components/onboarding/role-step";
import { useReport } from "@/components/onboarding/shared";
import { mirrorApi, type MirrorDocument, type Onboarding, type OnboardingUpdate, type RoleAnalysis } from "@/lib/api";
import { onboardingCopy } from "@/lib/copy-onboarding";

const t = onboardingCopy;
const STEPS = t.progress.steps.length;

/**
 * First-run setup: role, experience, review what was found, plan ready.
 * Every step saves to the profile, so leaving and coming back resumes here.
 * No practice is created: the person chooses to start one (or not) from the plan.
 */
export function OnboardingFlow({ initialOnboarding }: { initialOnboarding: Onboarding }) {
  const router = useRouter();
  const { error, report } = useReport();
  const [onboarding, setOnboarding] = useState(initialOnboarding);
  // Older saved progress could be on step 5; the plan is now the last step.
  const [step, setStep] = useState(Math.min(STEPS, Math.max(1, initialOnboarding.onboarding_step || 1)));
  const [role, setRole] = useState<RoleAnalysis | null>(null);
  const [brief, setBrief] = useState<MirrorDocument | null>(null);
  const [resume, setResume] = useState<MirrorDocument | null>(null);
  const [hydrating, setHydrating] = useState(true);

  useEffect(() => {
    let active = true;
    async function hydrate() {
      try {
        const [documents, savedRole] = await Promise.all([
          mirrorApi.documents(),
          initialOnboarding.onboarding_role_profile_id ? mirrorApi.role(initialOnboarding.onboarding_role_profile_id).catch(() => null) : null,
        ]);
        if (!active) return;
        const resumes = documents
          .filter((document) => document.document_type === "RESUME" && !document.archived_at)
          .sort((a, b) => b.created_at.localeCompare(a.created_at));
        const savedResume = resumes.find((document) => document.id === initialOnboarding.onboarding_resume_document_id) ?? resumes[0] ?? null;
        setResume(savedResume);
        setBrief(documents.find((document) => document.id === initialOnboarding.onboarding_role_brief_document_id) ?? null);
        setRole(savedRole);
        // Resume only where the saved work supports it.
        setStep((current) => (!savedRole ? 1 : !initialOnboarding.onboarding_resume_document_id ? Math.min(current, 2) : current));
      } catch (reason) {
        if (active) report(t.errors.restore, reason);
      } finally {
        if (active) setHydrating(false);
      }
    }
    void hydrate();
    return () => { active = false; };
  }, [initialOnboarding, report]);

  async function persist(values: OnboardingUpdate) {
    try {
      const updated = await mirrorApi.updateOnboarding(values);
      setOnboarding(updated);
      report("");
      return updated;
    } catch (reason) {
      report(t.errors.save, reason);
      return null;
    }
  }

  async function goTo(next: number, values: OnboardingUpdate = {}) {
    if (await persist({ ...values, onboarding_step: next })) setStep(next);
  }

  async function roleReady(setup: RoleSetup) {
    setRole(setup.role);
    setBrief(setup.brief);
    await goTo(2, {
      target_role: setup.role.target_role,
      target_company: setup.company || null,
      onboarding_role_brief_document_id: setup.brief?.id ?? null,
      onboarding_role_brief_skipped: setup.skipped,
      onboarding_role_profile_id: setup.role.id,
    });
  }

  async function resumeReady(document: MirrorDocument) {
    setResume(document);
    await goTo(3, { onboarding_resume_document_id: document.id });
  }

  // Finishing never depends on a practice existing; either exit completes setup first.
  async function exit(href: string) {
    if (!onboarding.onboarding_completed && !(await persist({ onboarding_completed: true }))) return;
    router.replace(href);
    router.refresh();
  }

  function renderStep() {
    if (step === 1 || !role) {
      return (
        <RoleStep
          initialRole={onboarding.target_role ?? ""}
          initialCompany={onboarding.target_company ?? ""}
          initialBrief={brief}
          initialSkipped={onboarding.onboarding_role_brief_skipped}
          reuse={role}
          report={report}
          onReady={roleReady}
        />
      );
    }
    if (step === 2) return <ExperienceStep saved={resume} report={report} onBack={() => void goTo(1)} onReady={resumeReady} />;
    if (step === 3) return <ReviewStep report={report} onBack={() => void goTo(2)} onDone={() => goTo(4)} />;
    return <PlanReadyStep roleProfileId={role.id} roleName={onboarding.target_role ?? role.target_role} report={report} onExit={exit} />;
  }

  const shown = role ? step : 1;
  return (
    <main id="main-content" className="op-flow" data-step={shown}>
      <nav className="op-progress" aria-label={t.progress.label(shown, STEPS)}>
        <ol>
          {t.progress.steps.map((label, index) => (
            <li key={label} aria-current={index + 1 === shown ? "step" : undefined} data-done={index + 1 < shown}>{label}</li>
          ))}
        </ol>
        <p className="op-muted">{t.progress.saved}</p>
      </nav>
      {hydrating ? <p role="status" className="op-muted">{t.progress.restoring}</p> : <div key={shown}>{renderStep()}</div>}
      {error && <p role="alert" className="ob-error">{error}</p>}
    </main>
  );
}
