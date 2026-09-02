import { redirect } from "next/navigation";

export default async function LegacyInterviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/app/interview/${id}`);
}

