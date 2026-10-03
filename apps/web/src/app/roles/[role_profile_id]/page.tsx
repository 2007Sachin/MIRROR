import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

/** The role view now lives in My plan. Only a view parameter is passed; nothing is changed. */
export default async function RoleDetailRoute({ params }: { params: Promise<{ role_profile_id: string }> }) {
  const { role_profile_id } = await params;
  redirect(`/plan?role=${encodeURIComponent(role_profile_id)}`);
}
