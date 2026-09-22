import { redirect } from "next/navigation";
import { getServerOnboarding } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function SessionsLayout({ children }: { children: React.ReactNode }) {
  const result = await getServerOnboarding();
  if (result.status === "unauthenticated") redirect("/login?reason=session_expired");
  if (result.status === "unavailable") {
    return (
      <main id="main-content" className="shell py-20">
        <p role="alert" className="text-sm text-[var(--silver)]">We couldn't check your setup just now. Please refresh and try again.</p>
      </main>
    );
  }
  if (!result.onboarding.onboarding_completed) redirect("/onboarding");
  return children;
}

