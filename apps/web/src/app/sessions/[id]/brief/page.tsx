import { ArrowRight, Check } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { Reveal } from "@/components/motion/reveal";
import { PracticeBriefNote } from "@/components/practice/practice-brief-note";
import "@/styles/sessions.css";

export default async function PreBriefPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const points = [
    "Questions are based on your resume, target role, and answers.",
    "Mirror may return to something you said earlier. That's just curiosity, never a sign that anything went badly.",
    "Your reflection is built from what comes up in this conversation.",
    "If there isn't enough to say, we'll say so instead of guessing.",
    "You're welcome to disagree with any part of your reflection afterward.",
  ];
  return (
    <main id="main-content" className="shell py-12 sm:py-20">
      <Reveal as="div" className="sb-shell">
        <p className="text-sm text-[var(--silver)]">Your session is ready</p>
        <h1 className="display mt-4 text-5xl font-semibold tracking-[-0.055em]">Before we begin</h1>
        <p className="mt-7 text-lg leading-8 text-[var(--silver)]">
          There are no trick questions here. You can pause, take your time, or stop whenever you need to.
        </p>
        <PracticeBriefNote sessionId={id} />
        <div className="sb-points">
          {points.map((point) => (
            <div key={point} className="sb-point">
              <Check size={18} className="mt-1 shrink-0 text-[var(--pulse)]" aria-hidden />
              <p>{point}</p>
            </div>
          ))}
        </div>
        <div className="mt-10 flex flex-col gap-3 sm:flex-row">
          <Link href={`/app/interview/${id}`} className="button-primary">Begin the conversation <ArrowRight size={18} /></Link>
        </div>
        <p className="mt-6 text-xs leading-5 text-[var(--silver)]">Allow about 20 minutes. There are no ratings or tips during the conversation; your reflection comes afterward.</p>
      </Reveal>
    </main>
  );
}

