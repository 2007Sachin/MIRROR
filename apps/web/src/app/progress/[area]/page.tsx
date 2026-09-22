import { redirect } from "next/navigation";

import { AreaDetail } from "@/components/progress/area-detail";
import { WorkspaceUnavailable } from "@/components/workspace/workspace-unavailable";
import { getServerOnboarding } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function AreaDetailRoute({ params }: { params: Promise<{ area: string }> }) {
  const result = await getServerOnboarding();
  if (result.status === "unauthenticated") redirect("/login?reason=session_expired");
  if (result.status === "unavailable") return <WorkspaceUnavailable />;
  if (!result.onboarding.onboarding_completed) redirect("/onboarding");
  const { area } = await params;
  return <AreaDetail areaKey={area} />;
}
