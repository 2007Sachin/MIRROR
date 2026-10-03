import { notFound, redirect } from "next/navigation";

import { DimensionAnswers } from "@/components/progress/dimension-answers";
import { WorkspaceUnavailable } from "@/components/workspace/workspace-unavailable";
import { isUuid } from "@/lib/progress-view";
import { getServerOnboarding } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function DimensionAnswersRoute({
  params,
  searchParams,
}: {
  params: Promise<{ roleProfileId: string; dimension: string }>;
  searchParams: Promise<{ practice?: string }>;
}) {
  const result = await getServerOnboarding();
  if (result.status === "unauthenticated") redirect("/login?reason=session_expired");
  if (result.status === "unavailable") return <WorkspaceUnavailable />;
  if (!result.onboarding.onboarding_completed) redirect("/onboarding");
  const { roleProfileId, dimension } = await params;
  if (!isUuid(roleProfileId)) notFound();
  const { practice } = await searchParams;
  return (
    <DimensionAnswers
      roleProfileId={roleProfileId}
      dimensionKey={dimension}
      practiceSessionId={practice && isUuid(practice) ? practice : undefined}
    />
  );
}
