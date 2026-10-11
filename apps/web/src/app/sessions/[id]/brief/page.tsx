import { redirect } from "next/navigation";

/**
 * The session brief now lives in the interview room's pre-join (redesign P7). Bookmarked and
 * older links keep working: the same session opens in the room, which checks its status.
 */
export default async function SessionBriefRedirect({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/app/interview/${encodeURIComponent(id)}`);
}
