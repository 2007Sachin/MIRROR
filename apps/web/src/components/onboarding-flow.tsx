"use client";

import { ArrowLeft, ArrowRight, Check } from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import {
  ApiError,
  mirrorApi,
  type CareerIntent,
  type CareerStage,
  type InterviewTimeline,
  type Onboarding,
  type OnboardingUpdate,
  type PreferredLanguage,
} from "@/lib/api";
import { getSupabaseBrowserClient } from "@/lib/supabase";

type Choice<T extends string> = { value: T; label: string };

const careerStages: Choice<CareerStage>[] = [
  { value: "STUDENT", label: "Student" },
  { value: "FINAL_YEAR_STUDENT", label: "Final-year student" },
  { value: "FRESHER", label: "Fresher" },
  { value: "EARLY_CAREER", label: "Early career" },
  { value: "EXPERIENCED", label: "Experienced" },
];

const careerIntents: Choice<CareerIntent>[] = [
  { value: "CAMPUS_PLACEMENT", label: "Campus placement" },
  { value: "INTERNSHIP", label: "Internship" },
  { value: "FIRST_JOB", label: "First job" },
  { value: "JOB_SWITCH", label: "Switching roles" },
  { value: "SPECIFIC_COMPANY", label: "Specific company interview" },
  { value: "EXPLORING", label: "Just exploring" },
];

const timelines: Choice<InterviewTimeline>[] = [
  { value: "TODAY", label: "Today" },
  { value: "THIS_WEEK", label: "This week" },
  { value: "THIS_MONTH", label: "This month" },
  { value: "LATER", label: "Later" },
  { value: "EXPLORING", label: "Just exploring" },
];

const languages: Choice<PreferredLanguage>[] = [
  { value: "ENGLISH", label: "English" },
  { value: "HINDI", label: "Hindi" },
  { value: "KANNADA", label: "Kannada" },
  { value: "TAMIL", label: "Tamil" },
  { value: "TELUGU", label: "Telugu" },
];

const roleSuggestions = [
  "Software Engineer",
  "Data Analyst",
  "Product Manager",
  "Product Designer",
  "Business Analyst",
  "Marketing Associate",
  "Sales Development Representative",
  "Customer Success Manager",
];

function firstIncompleteStep(onboarding: Onboarding) {
  const hasProgress = Boolean(
    onboarding.career_stage
    || onboarding.career_intent
    || onboarding.target_role
    || onboarding.interview_timeline
    || onboarding.preferred_language,
  );
  if (!hasProgress) return 0;
  if (!onboarding.career_stage || !onboarding.career_intent) return 1;
  if (!onboarding.target_role) return 2;
  if (!onboarding.interview_timeline) return 3;
  if (!onboarding.preferred_language) return 4;
  return 5;
}

function ChoiceCards<T extends string>({
  options,
  value,
  onChange,
  compact = false,
}: {
  options: Choice<T>[];
  value: T | null;
  onChange: (value: T) => void;
  compact?: boolean;
}) {
  return (
    <div className={compact ? "flex flex-wrap gap-2" : "grid gap-3 sm:grid-cols-2"}>
      {options.map((option) => {
        const selected = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected}
            onClick={() => onChange(option.value)}
            className={[
              "flex items-center justify-between rounded-lg border text-left transition-colors",
              compact ? "min-h-10 px-3 py-2 text-sm" : "min-h-16 px-4 py-3 font-semibold",
              selected
                ? "border-[var(--pulse)] bg-[rgba(79,209,165,.08)] text-[var(--paper)]"
                : "hairline bg-[rgba(42,46,40,.2)] text-[var(--silver)] hover:text-[var(--paper)]",
            ].join(" ")}
          >
            {option.label}
            {selected && <Check size={17} aria-hidden="true" />}
          </button>
        );
      })}
    </div>
  );
}

function StepFrame({ step, children }: { step: number; children: React.ReactNode }) {
  return (
    <main className="shell py-12 sm:py-20">
      <div className="mx-auto max-w-2xl">
        <div className="mb-10 flex items-center gap-4" aria-label={`Step ${step + 1} of 6`}>
          <span className="mono text-[10px] uppercase tracking-[0.18em] text-[var(--silver)]">Setup {step + 1}/6</span>
          <div className="h-px flex-1 bg-[var(--line)]"><div className="h-px bg-[var(--pulse)]" style={{ width: `${((step + 1) / 6) * 100}%` }} /></div>
        </div>
        {children}
      </div>
    </main>
  );
}

export function OnboardingFlow({ initialOnboarding }: { initialOnboarding: Onboarding }) {
  const router = useRouter();
  const [onboarding, setOnboarding] = useState(initialOnboarding);
  const [step, setStep] = useState(() => firstIncompleteStep(initialOnboarding));
  const [stage, setStage] = useState<CareerStage | null>(initialOnboarding.career_stage);
  const [intent, setIntent] = useState<CareerIntent | null>(initialOnboarding.career_intent);
  const [targetRole, setTargetRole] = useState(initialOnboarding.target_role ?? "");
  const [timeline, setTimeline] = useState<InterviewTimeline | null>(initialOnboarding.interview_timeline);
  const [language, setLanguage] = useState<PreferredLanguage | null>(initialOnboarding.preferred_language);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function save(values: OnboardingUpdate, nextStep: number) {
    setSaving(true);
    setError("");
    try {
      const updated = await mirrorApi.updateOnboarding(values);
      setOnboarding(updated);
      setStep(nextStep);
      return true;
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) {
        await getSupabaseBrowserClient().auth.signOut();
        router.replace("/login?reason=session_expired");
      } else {
        setError("Mirror could not save this step. Check your connection and try again.");
      }
      return false;
    } finally {
      setSaving(false);
    }
  }

  const backButton = step > 1 && (
    <button type="button" className="button-secondary" disabled={saving} onClick={() => { setError(""); setStep(step - 1); }}>
      <ArrowLeft size={17} /> Back
    </button>
  );
  const errorMessage = error && <p role="alert" className="mt-5 border-l-2 border-red-400 pl-3 text-sm text-red-200">{error}</p>;

  if (step === 0) {
    return (
      <StepFrame step={step}>
        <p className="mono text-[10px] uppercase tracking-[0.18em] text-[var(--silver)]">A clearer starting point</p>
        <h1 className="display mt-5 max-w-[18ch] text-5xl leading-[.98] font-semibold tracking-[-0.055em] sm:text-6xl">Know what happens when your answers are challenged.</h1>
        <p className="mt-7 max-w-xl leading-7 text-[var(--silver)]">A few details will help Mirror prepare the right interview context later. You can update these preferences again.</p>
        <button type="button" className="button-primary mt-10" onClick={() => setStep(1)}>Set up my Mirror <ArrowRight size={18} /></button>
      </StepFrame>
    );
  }

  if (step === 1) {
    return (
      <StepFrame step={step}>
        <h1 className="display text-4xl font-semibold tracking-[-0.045em]">What are you preparing for?</h1>
        <div className="mt-8"><ChoiceCards options={careerIntents} value={intent} onChange={setIntent} /></div>
        <div className="mt-10 border-t hairline pt-7">
          <h2 className="text-sm font-semibold">Where are you in your career?</h2>
          <div className="mt-4"><ChoiceCards options={careerStages} value={stage} onChange={setStage} compact /></div>
        </div>
        {errorMessage}
        <div className="mt-9 flex justify-end">
          <button type="button" className="button-primary" disabled={!intent || !stage || saving} onClick={() => intent && stage && save({ career_intent: intent, career_stage: stage }, 2)}>
            {saving ? "Saving…" : "Continue"} {!saving && <ArrowRight size={18} />}
          </button>
        </div>
      </StepFrame>
    );
  }

  if (step === 2) {
    return (
      <StepFrame step={step}>
        <h1 className="display text-4xl font-semibold tracking-[-0.045em]">What role are you targeting?</h1>
        <p className="mt-4 text-sm leading-6 text-[var(--silver)]">Start typing a role. A precise title is useful, but it does not need to match a fixed database.</p>
        <form className="mt-8" onSubmit={(event: FormEvent) => { event.preventDefault(); save({ target_role: targetRole }, 3); }}>
          <label className="block">
            <span className="mb-2 block text-sm font-semibold">Target role</span>
            <input className="field" list="target-role-suggestions" value={targetRole} onChange={(event) => setTargetRole(event.target.value)} minLength={2} maxLength={160} required autoFocus placeholder="e.g. Product Designer" />
            <datalist id="target-role-suggestions">{roleSuggestions.map((role) => <option key={role} value={role} />)}</datalist>
          </label>
          {errorMessage}
          <div className="mt-9 flex items-center justify-between">{backButton}<button type="submit" className="button-primary" disabled={targetRole.trim().length < 2 || saving}>{saving ? "Saving…" : "Continue"} {!saving && <ArrowRight size={18} />}</button></div>
        </form>
      </StepFrame>
    );
  }

  if (step === 3) {
    return (
      <StepFrame step={step}>
        <h1 className="display text-4xl font-semibold tracking-[-0.045em]">How soon are you preparing for an interview?</h1>
        <div className="mt-8"><ChoiceCards options={timelines} value={timeline} onChange={setTimeline} /></div>
        {errorMessage}
        <div className="mt-9 flex items-center justify-between">{backButton}<button type="button" className="button-primary" disabled={!timeline || saving} onClick={() => timeline && save({ interview_timeline: timeline }, 4)}>{saving ? "Saving…" : "Continue"} {!saving && <ArrowRight size={18} />}</button></div>
      </StepFrame>
    );
  }

  if (step === 4) {
    return (
      <StepFrame step={step}>
        <h1 className="display text-4xl font-semibold tracking-[-0.045em]">Which language do you prefer?</h1>
        <p className="mt-4 text-sm leading-6 text-[var(--silver)]">This saves your preference only. Interviews remain in English for now.</p>
        <div className="mt-8"><ChoiceCards options={languages} value={language} onChange={setLanguage} /></div>
        {errorMessage}
        <div className="mt-9 flex items-center justify-between">{backButton}<button type="button" className="button-primary" disabled={!language || saving} onClick={() => language && save({ preferred_language: language }, 5)}>{saving ? "Saving…" : "Continue"} {!saving && <ArrowRight size={18} />}</button></div>
      </StepFrame>
    );
  }

  const summary = [
    { label: "Target role", value: onboarding.target_role },
    { label: "Intent", value: careerIntents.find((item) => item.value === onboarding.career_intent)?.label },
    { label: "Timeline", value: timelines.find((item) => item.value === onboarding.interview_timeline)?.label },
  ];
  return (
    <StepFrame step={step}>
      <p className="mono text-[10px] uppercase tracking-[0.18em] text-[var(--silver)]">Ready to begin</p>
      <h1 className="display mt-5 text-4xl font-semibold tracking-[-0.045em]">Your Mirror is set up.</h1>
      <dl className="mt-9 divide-y divide-[var(--line)] border-y hairline">
        {summary.map((item) => <div key={item.label} className="grid grid-cols-[8rem_1fr] gap-4 py-5"><dt className="text-sm text-[var(--silver)]">{item.label}</dt><dd className="font-semibold">{item.value}</dd></div>)}
      </dl>
      {errorMessage}
      <div className="mt-9 flex items-center justify-between">{backButton}<button type="button" className="button-primary" disabled={saving} onClick={async () => { if (await save({ onboarding_completed: true }, 5)) { router.replace("/app/setup"); router.refresh(); } }}>{saving ? "Saving…" : "Continue"} {!saving && <ArrowRight size={18} />}</button></div>
    </StepFrame>
  );
}

