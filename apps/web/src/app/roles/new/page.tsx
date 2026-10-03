import { redirect } from "next/navigation";

import { NewRoleFlow } from "@/components/onboarding/new-role-flow";
import { WorkspaceUnavailable } from "@/components/workspace/workspace-unavailable";
import { getServerOnboarding } from "@/lib/server-api";

export const dynamic = "force-dynamic";

/** Set up another role: role details, then its plan. No practice is created here. */
export default async function NewRole() {
  const result = await getServerOnboarding();
  if (result.status === "unauthenticated") redirect("/login?reason=session_expired");
  if (result.status === "unavailable") return <WorkspaceUnavailable />;
  if (!result.onboarding.onboarding_completed) redirect("/onboarding");
  return <NewRoleFlow />;
}
