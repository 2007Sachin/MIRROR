import { redirect } from "next/navigation";

import { ProgressPage } from "@/components/progress/progress-page";
import { WorkspaceUnavailable } from "@/components/workspace/workspace-unavailable";
import { getServerOnboarding } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function Progress({ searchParams }: { searchParams: Promise<{ role?: string; area?: string }> }) {
  const result = await getServerOnboarding();
  if (result.status === "unauthenticated") redirect("/login?reason=session_expired");
  if (result.status === "unavailable") return <WorkspaceUnavailable />;
  if (!result.onboarding.onboarding_completed) redirect("/onboarding");
  const { role, area } = await searchParams;
  // Links written before development areas had their own page still work.
  if (area) redirect(`/progress/${encodeURIComponent(area)}`);
  return <ProgressPage initialRole={role} />;
}
