import { notFound } from "next/navigation";

import { InterviewBriefPage } from "@/components/interviews/interview-brief-page";
import { InterviewsPage } from "@/components/interviews/interviews-page";
import { interviewsQaFixtures, interviewsQaScreen } from "@/lib/interviews-qa-fixtures";

export const dynamic = "force-dynamic";

/** Local-only harness: the real Interviews components without the onboarding guard. See docs/architecture/HOME_QA.md. */
export default async function InterviewsQaPage({ searchParams }: { searchParams: Promise<{ screen?: string }> }) {
  if (process.env.NODE_ENV === "production" || process.env.MIRROR_HOME_QA !== "1") notFound();
  const eventId = interviewsQaFixtures.screens[interviewsQaScreen((await searchParams).screen)];
  const roleId = interviewsQaFixtures.roleId;
  return eventId ? <InterviewBriefPage roleProfileId={roleId} eventId={eventId} /> : <InterviewsPage roleProfileId={roleId} />;
}
