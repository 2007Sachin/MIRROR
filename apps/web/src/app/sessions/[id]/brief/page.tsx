import { ArrowRight, Check } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";

export default async function PreBriefPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const points = [
    "Questions are based on your resume, target role, and answers.",
    "Mirror may return to something you said earlier.",
    "The final report uses evidence captured during this interview.",
    "Thin evidence appears as Not enough signal rather than a guessed score.",
    "You can disagree with individual assessments after the session.",
  ];
  return (
    <main className="shell py-12 sm:py-20">
      <div className="mx-auto max-w-3xl">
        <p className="text-sm text-[var(--silver)]">Session prepared</p>
        <h1 className="display mt-4 text-5xl font-semibold tracking-[-0.055em]">Before we begin</h1>
        <p className="mt-7 text-lg leading-8 text-[var(--silver)]">
          Some answers may be challenged or revisited. This does not automatically mean Mirror has concluded you were wrong.
        </p>
        <div className="mt-10 divide-y divide-[var(--line)] border-y hairline">
          {points.map((point) => (
            <div key={point} className="flex gap-4 py-4 text-sm leading-6">
              <Check size={18} className="mt-1 shrink-0 text-[var(--pulse)]" aria-hidden />
              <p>{point}</p>
            </div>
          ))}
        </div>
        <div className="mt-10 flex flex-col gap-3 sm:flex-row">
          <Link href={`/app/interview/${id}`} className="button-primary">Begin interview <ArrowRight size={18} /></Link>
        </div>
        <p className="mt-6 text-xs leading-5 text-[var(--silver)]">Allow about 20 minutes. No scores or coaching appear during the interview.</p>
      </div>
    </main>
  );
}

