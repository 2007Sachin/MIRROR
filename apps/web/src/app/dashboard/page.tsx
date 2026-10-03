import { redirect } from "next/navigation";

import { HomePage } from "@/components/dashboard/home-page";
import { WorkspaceUnavailable } from "@/components/workspace/workspace-unavailable";
import { getServerOnboarding } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function DashboardPage({ searchParams }: { searchParams: Promise<{ role?: string }> }) {
  const result = await getServerOnboarding();
  if (result.status === "unauthenticated") {
    redirect("/login?reason=session_expired");
  }
  if (result.status === "unavailable") {
    return <WorkspaceUnavailable />;
  }
  if (!result.onboarding.onboarding_completed) redirect("/onboarding");
  const { role } = await searchParams;
  return <HomePage initialRole={role} />;
}
