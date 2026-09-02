import { VoiceInterview } from "@/components/voice-interview";

export default async function InterviewPage({
  params,
}: {
  params: Promise<{ session_id: string }>;
}) {
  const { session_id: sessionId } = await params;
  return <VoiceInterview sessionId={sessionId} />;
}

