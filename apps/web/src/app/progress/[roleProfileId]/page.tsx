import { notFound, redirect } from "next/navigation";

import { RoleProgressPage } from "@/components/progress/role-progress";
import { WorkspaceUnavailable } from "@/components/workspace/workspace-unavailable";
import { isRoleTab, isUuid } from "@/lib/progress-view";
import { getServerOnboarding } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function RoleProgressRoute({
  params,
  searchParams,
}: {
  params: Promise<{ roleProfileId: string }>;
  searchParams: Promise<{ tab?: string }>;
}) {
  const result = await getServerOnboarding();
  if (result.status === "unauthenticated") redirect("/login?reason=session_expired");
  if (result.status === "unavailable") return <WorkspaceUnavailable />;
  if (!result.onboarding.onboarding_completed) redirect("/onboarding");
  const { roleProfileId } = await params;
  if (!isUuid(roleProfileId)) notFound();
  const { tab } = await searchParams;
  return <RoleProgressPage roleProfileId={roleProfileId} tab={isRoleTab(tab) ? tab : "overview"} />;
}
