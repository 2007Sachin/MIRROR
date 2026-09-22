import { redirect } from "next/navigation";

import { EvidenceDashboard } from "@/components/evidence-dashboard";
import { WorkspaceUnavailable } from "@/components/workspace/workspace-unavailable";
import { getServerOnboarding } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const result = await getServerOnboarding();
  if (result.status === "unauthenticated") {
    redirect("/login?reason=session_expired");
  }
  if (result.status === "unavailable") {
    return <WorkspaceUnavailable />;
  }
  if (!result.onboarding.onboarding_completed) redirect("/onboarding");
  return <EvidenceDashboard initialOnboarding={result.onboarding} />;
}
