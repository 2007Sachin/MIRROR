import { redirect } from "next/navigation";

import { PressureTestPage } from "@/components/roles/pressure-test-page";
import { WorkspaceUnavailable } from "@/components/workspace/workspace-unavailable";
import { getServerOnboarding } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function PressureTestRoute({ params }: { params: Promise<{ role_profile_id: string }> }) {
  const result = await getServerOnboarding();
  if (result.status === "unauthenticated") redirect("/login?reason=session_expired");
  if (result.status === "unavailable") return <WorkspaceUnavailable />;
  if (!result.onboarding.onboarding_completed) redirect("/onboarding");
  const { role_profile_id } = await params;
  return <PressureTestPage roleProfileId={role_profile_id} />;
}
