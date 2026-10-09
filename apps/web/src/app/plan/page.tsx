import { redirect } from "next/navigation";

import { PlanPage } from "@/components/plan/plan-page";
import { WorkspaceUnavailable } from "@/components/workspace/workspace-unavailable";
import { getServerOnboarding } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function Plan({ searchParams }: { searchParams: Promise<{ role?: string | string[]; target?: string | string[] }> }) {
  const result = await getServerOnboarding();
  if (result.status === "unauthenticated") redirect("/login?reason=session_expired");
  if (result.status === "unavailable") return <WorkspaceUnavailable />;
  if (!result.onboarding.onboarding_completed) redirect("/onboarding");
  const { role, target } = await searchParams;
  return <PlanPage roleProfileId={typeof role === "string" && role ? role : null} initialTargetId={typeof target === "string" && target ? target : null} />;
}
