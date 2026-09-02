"use client";

import { ArrowDown, ArrowRight, Check, CircleNotch, FileMagnifyingGlass, Quotes, ShieldCheck } from "@phosphor-icons/react";
import Link from "next/link";
import { useState } from "react";
import { MirrorOrb } from "@/components/mirror-orb";

const auditSteps = [
  { label: "Resume claim", detail: "Built the data pipeline" },
  { label: "Under questioning", detail: "I handled the transformation layer. A teammate owned ingestion." },
  { label: "Evidence verdict", detail: "Ownership clarified, outcome still needs a measurement" },
] as const;

export function LandingStory() {
  const [activeStep, setActiveStep] = useState(0);
  return (
    <main>
      <section className="shell grid min-h-[calc(100dvh-4rem)] items-center gap-12 py-14 lg:grid-cols-[.94fr_1.06fr] lg:gap-20 lg:py-20">
        <div className="max-w-2xl">
          <p className="mb-7 text-sm text-[var(--pulse)]">Interview diagnostic and claims audit</p>
          <h1 className="display max-w-[13ch] text-5xl leading-[.93] font-semibold tracking-[-0.06em] sm:text-7xl lg:text-[5.35rem]">Your answers deserve more than a thumbs-up.</h1>
          <p className="mt-8 max-w-[55ch] text-lg leading-8 text-[var(--silver)]">Mirror is the interview that tests whether your resume claims hold when a real person asks one more question.</p>
          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <Link href="/signup" className="button-primary">Run a diagnostic <ArrowRight size={18} /></Link>
            <a href="#why" className="button-secondary">Understand the problem <ArrowDown size={18} /></a>
          </div>
          <p className="mono mt-7 text-[10px] uppercase tracking-[0.16em] text-[var(--silver)]">No live score · no coaching · evidence after the session</p>
        </div>
        <div className="relative flex min-h-[26rem] items-center justify-center border-y hairline py-8 lg:border-y-0 lg:border-l lg:py-0">
          <MirrorOrb activeStep={activeStep} />
        </div>
      </section>

      <section id="why" className="border-y hairline">
        <div className="shell grid gap-12 py-20 lg:grid-cols-[.8fr_1.2fr] lg:gap-24 lg:py-28">
          <div><p className="mono text-[10px] uppercase tracking-[0.18em] text-[var(--silver)]">The existing problem</p><h2 className="display mt-5 max-w-[14ch] text-4xl leading-[.98] font-semibold tracking-[-0.05em] sm:text-5xl">Most practice interviews stop before the useful part.</h2></div>
          <div className="grid gap-8 sm:grid-cols-2"><article className="border-t hairline pt-5"><p className="mono text-xs text-[var(--pulse)]">01</p><h3 className="display mt-5 text-xl font-semibold">A fluent answer can still be thin.</h3><p className="mt-3 text-sm leading-6 text-[var(--silver)]">Most tools reward confidence in the moment. They do not ask where the number came from, who made the decision, or what changed after the launch.</p></article><article className="border-t hairline pt-5"><p className="mono text-xs text-[var(--pulse)]">02</p><h3 className="display mt-5 text-xl font-semibold">A generic score cannot show you why.</h3><p className="mt-3 text-sm leading-6 text-[var(--silver)]">A single percentage compresses skill, communication, and uncertainty into a number you cannot inspect or dispute.</p></article></div>
        </div>
      </section>

      <section className="shell grid gap-14 py-20 lg:grid-cols-[.75fr_1.25fr] lg:py-28"><div><p className="mono text-[10px] uppercase tracking-[0.18em] text-[var(--silver)]">The Mirror method</p><h2 className="display mt-5 max-w-[12ch] text-4xl leading-[.98] font-semibold tracking-[-0.05em] sm:text-5xl">A diagnostic, not a pep talk.</h2><p className="mt-6 max-w-[42ch] leading-7 text-[var(--silver)]">We compare three sources of truth: what your resume says, what the role needs, and what survives your own explanation.</p><div className="mt-8 flex items-start gap-3 border-t hairline pt-5 text-sm leading-6 text-[var(--silver)]"><ShieldCheck size={20} className="mt-0.5 shrink-0 text-[var(--pulse)]" /><p>Every major judgment points back to a moment in your transcript.</p></div></div><div className="border-t hairline pt-6"><div className="flex flex-wrap gap-2" role="tablist" aria-label="Claims audit example">{auditSteps.map((step, index) => <button key={step.label} type="button" role="tab" aria-selected={activeStep === index} onClick={() => setActiveStep(index)} className={`rounded-full border px-4 py-2 text-sm transition ${activeStep === index ? "border-[var(--pulse)] text-[var(--paper)]" : "border-[var(--line)] text-[var(--silver)] hover:border-[rgba(237,238,234,.4)]"}`}>{step.label}</button>)}</div><div className="mt-10 grid gap-6 sm:grid-cols-[auto_1fr] sm:gap-9"><div className="mono text-xs text-[var(--silver)]">0{activeStep + 1}</div><div><p className="display text-3xl leading-tight font-medium tracking-[-0.04em]">{auditSteps[activeStep].detail}</p><p className="mt-5 max-w-[50ch] text-sm leading-6 text-[var(--silver)]">{activeStep === 0 ? "Mirror starts with a claim anchored to a source, not a vibe." : activeStep === 1 ? "The next question is chosen to clarify scope, ownership, or measurement without coaching you toward a preferred answer." : "The report keeps the nuance: held, partially held, walked back, contradicted, or not enough signal."}</p></div></div><div className="mt-12 flex items-center gap-3 text-xs text-[var(--silver)]"><CircleNotch size={16} className="text-[var(--pulse)]" /><span>Click each step to trace one claim from source to verdict.</span></div></div></section>

      <section className="bg-[var(--slate)]"><div className="shell grid gap-12 py-20 lg:grid-cols-[1.1fr_.9fr] lg:items-end lg:py-28"><div><p className="mono text-[10px] uppercase tracking-[0.18em] text-[var(--silver)]">Why people choose Mirror</p><h2 className="display mt-5 max-w-[15ch] text-4xl leading-[.98] font-semibold tracking-[-0.05em] sm:text-5xl">Leave with something you can actually use.</h2><p className="mt-6 max-w-[48ch] text-lg leading-8 text-[var(--silver)]">Not a badge. Not a leaderboard. A private diagnostic report that tells you where your story became less precise and what to practice next.</p></div><div className="space-y-4 text-sm leading-6"><div className="flex gap-3 border-t hairline pt-4"><FileMagnifyingGlass size={20} className="mt-0.5 shrink-0 text-[var(--pulse)]" /><p>Claims Audit with source, status, and transcript evidence.</p></div><div className="flex gap-3 border-t hairline pt-4"><Quotes size={20} className="mt-0.5 shrink-0 text-[var(--pulse)]" /><p>Separate Role Readiness from Interview Readiness.</p></div><div className="flex gap-3 border-t hairline pt-4"><Check size={20} className="mt-0.5 shrink-0 text-[var(--pulse)]" /><p>Uncertainty stays visible as Not enough signal.</p></div></div></div></section>

      <section className="shell grid gap-8 py-20 sm:grid-cols-[1fr_auto] sm:items-end lg:py-28"><div><p className="mono text-[10px] uppercase tracking-[0.18em] text-[var(--silver)]">Start with the evidence</p><h2 className="display mt-5 max-w-[13ch] text-4xl leading-[.98] font-semibold tracking-[-0.05em] sm:text-5xl">Find out what holds before someone else does.</h2></div><Link href="/signup" className="button-primary">Run a diagnostic <ArrowRight size={18} /></Link></section>

      <footer className="border-t hairline"><div className="shell flex flex-col gap-3 py-8 text-xs leading-5 text-[var(--silver)] sm:flex-row sm:items-center sm:justify-between"><p>Mirror evaluates evidence from this session. AI can make mistakes. Outcome validation is still in progress.</p><p className="mono">by Pathwisse</p></div></footer>
    </main>
  );
}

