import { redirect } from "next/navigation";

import { RoleDetail } from "@/components/roles/role-detail";
import { WorkspaceUnavailable } from "@/components/workspace/workspace-unavailable";
import { getServerOnboarding } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function RoleDetailRoute({ params }: { params: Promise<{ role_profile_id: string }> }) {
  const result = await getServerOnboarding();
  if (result.status === "unauthenticated") redirect("/login?reason=session_expired");
  if (result.status === "unavailable") return <WorkspaceUnavailable />;
  if (!result.onboarding.onboarding_completed) redirect("/onboarding");
  const { role_profile_id } = await params;
  return <RoleDetail roleProfileId={role_profile_id} />;
}
