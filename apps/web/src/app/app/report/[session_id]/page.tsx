import { ReviewPage } from "@/components/review/review-page";

export const dynamic = "force-dynamic";

export default async function ReviewRoute({ params }: { params: Promise<{ session_id: string }> }) {
  const { session_id } = await params;
  return <ReviewPage sessionId={session_id} />;
}
