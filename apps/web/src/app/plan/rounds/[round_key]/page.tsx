import { redirect } from "next/navigation";

import { RoundPage } from "@/components/plan/round-page";
import { WorkspaceUnavailable } from "@/components/workspace/workspace-unavailable";
import { getServerOnboarding } from "@/lib/server-api";

export const dynamic = "force-dynamic";

/** One practice round of a role's interview target. The role always travels in `?role=`. */
export default async function PlanRound({
  params,
  searchParams,
}: {
  params: Promise<{ round_key: string }>;
  searchParams: Promise<{ role?: string | string[] }>;
}) {
  const result = await getServerOnboarding();
  if (result.status === "unauthenticated") redirect("/login?reason=session_expired");
  if (result.status === "unavailable") return <WorkspaceUnavailable />;
  if (!result.onboarding.onboarding_completed) redirect("/onboarding");
  const [{ round_key }, { role }] = await Promise.all([params, searchParams]);
  // Without a role there is no target to read; My plan resolves the current role and pins it.
  if (typeof role !== "string" || !role) redirect("/plan");
  return <RoundPage roleProfileId={role} roundKey={round_key} />;
}
