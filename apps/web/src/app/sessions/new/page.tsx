"use client";

import { ArrowRight, FileText, LockKey } from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { mirrorApi } from "@/lib/api";

export default function NewSessionPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    const form = new FormData(event.currentTarget);
    const resume = form.get("resume");
    try {
      if (!(resume instanceof File) || resume.size === 0) throw new Error("Choose a PDF or DOCX resume.");
      const session = await mirrorApi.createSession(String(form.get("target_role")), String(form.get("jd_text")));
      await mirrorApi.uploadResume(session.id, resume);
      await mirrorApi.prepare(session.id);
      router.push(`/sessions/${session.id}/brief`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The session could not be created.");
      setBusy(false);
    }
  }

  return (
    <main className="shell py-12 sm:py-16">
      <div className="grid gap-12 lg:grid-cols-[.72fr_1.28fr]">
        <section>
          <p className="text-sm text-[var(--silver)]">New diagnostic</p>
          <h1 className="display mt-4 text-4xl font-semibold tracking-[-0.05em] sm:text-5xl">Give Mirror the evidence it needs.</h1>
          <p className="mt-6 max-w-[42ch] leading-7 text-[var(--silver)]">Your resume sets the claims to examine. The job description sets the competencies to investigate.</p>
          <div className="mt-10 flex items-start gap-3 border-t hairline pt-5 text-sm leading-6 text-[var(--silver)]">
            <LockKey size={20} className="mt-0.5 shrink-0 text-[var(--pulse)]" />
            <p>Resumes and interview data are isolated per candidate and are not intentionally used to train third-party models.</p>
          </div>
        </section>

        <form onSubmit={submit} className="space-y-7 border-t hairline pt-7" aria-busy={busy}>
          <label className="block">
            <span className="mb-2 block text-sm font-semibold">Target role</span>
            <input className="field" name="target_role" required minLength={2} maxLength={160} placeholder="Data Analyst" />
          </label>
          <label className="block">
            <span className="mb-2 block text-sm font-semibold">Resume</span>
            <span className="field flex cursor-pointer items-center gap-3 text-[var(--silver)]">
              <FileText size={20} /> <span>PDF or DOCX, up to 8 MB</span>
              <input className="sr-only" name="resume" type="file" required accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" />
            </span>
          </label>
          <label className="block">
            <span className="mb-2 block text-sm font-semibold">Job description</span>
            <textarea className="field min-h-56 resize-y" name="jd_text" required minLength={50} maxLength={80000} placeholder="Paste the responsibilities, requirements, and role context." />
          </label>
          {error ? <p role="alert" className="border-l-2 border-red-400 pl-3 text-sm text-red-200">{error}</p> : null}
          <button className="button-primary w-full sm:w-auto" disabled={busy}>
            {busy ? "Preparing diagnostic..." : "Continue to pre-brief"} {!busy && <ArrowRight size={18} />}
          </button>
        </form>
      </div>
    </main>
  );
}


