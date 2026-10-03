import { notFound, redirect } from "next/navigation";

import { DimensionDetail } from "@/components/progress/dimension-detail";
import { WorkspaceUnavailable } from "@/components/workspace/workspace-unavailable";
import { isUuid } from "@/lib/progress-view";
import { getServerOnboarding } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function DimensionRoute({ params }: { params: Promise<{ roleProfileId: string; dimension: string }> }) {
  const result = await getServerOnboarding();
  if (result.status === "unauthenticated") redirect("/login?reason=session_expired");
  if (result.status === "unavailable") return <WorkspaceUnavailable />;
  if (!result.onboarding.onboarding_completed) redirect("/onboarding");
  const { roleProfileId, dimension } = await params;
  if (!isUuid(roleProfileId)) notFound();
  return <DimensionDetail roleProfileId={roleProfileId} dimensionKey={dimension} />;
}
