import { notFound, redirect } from "next/navigation";

import { AnswerDetail } from "@/components/progress/answer-detail";
import { WorkspaceUnavailable } from "@/components/workspace/workspace-unavailable";
import { isUuid } from "@/lib/progress-view";
import { getServerOnboarding } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function AnswerRoute({
  params,
  searchParams,
}: {
  params: Promise<{ roleProfileId: string; sessionId: string; turnId: string }>;
  searchParams: Promise<{ dimension?: string }>;
}) {
  const result = await getServerOnboarding();
  if (result.status === "unauthenticated") redirect("/login?reason=session_expired");
  if (result.status === "unavailable") return <WorkspaceUnavailable />;
  if (!result.onboarding.onboarding_completed) redirect("/onboarding");
  const { roleProfileId, sessionId, turnId } = await params;
  if (![roleProfileId, sessionId, turnId].every(isUuid)) notFound();
  const { dimension } = await searchParams;
  return <AnswerDetail roleProfileId={roleProfileId} sessionId={sessionId} turnId={turnId} dimension={dimension ?? null} />;
}
