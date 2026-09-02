import { createSupabaseServerClient } from "@/lib/supabase-server";
import type { Onboarding } from "@/lib/api";

type ServerOnboardingResult =
  | { status: "ok"; onboarding: Onboarding }
  | { status: "unauthenticated" }
  | { status: "unavailable" };

export async function getServerOnboarding(): Promise<ServerOnboardingResult> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return { status: "unauthenticated" };

  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.access_token) return { status: "unauthenticated" };

  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const response = await fetch(`${apiUrl}/api/v1/onboarding`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
      cache: "no-store",
    });
    if (response.status === 401) return { status: "unauthenticated" };
    if (!response.ok) return { status: "unavailable" };
    return { status: "ok", onboarding: await response.json() as Onboarding };
  } catch {
    return { status: "unavailable" };
  }
}

