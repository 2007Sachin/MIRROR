import { redirect } from "next/navigation";

import { StoryEditor } from "@/components/stories/story-editor";
import { WorkspaceUnavailable } from "@/components/workspace/workspace-unavailable";
import { getServerOnboarding } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function StoryRoute({ params }: { params: Promise<{ story_id: string }> }) {
  const result = await getServerOnboarding();
  if (result.status === "unauthenticated") redirect("/login?reason=session_expired");
  if (result.status === "unavailable") return <WorkspaceUnavailable />;
  if (!result.onboarding.onboarding_completed) redirect("/onboarding");
  const { story_id } = await params;
  return <StoryEditor storyId={story_id} />;
}
