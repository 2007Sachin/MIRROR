"use client";

import { SignOut } from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, mirrorApi, type Profile } from "@/lib/api";
import { getSupabaseBrowserClient } from "@/lib/supabase";

export function AppHome() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    mirrorApi.me()
      .then((value) => active && setProfile(value))
      .catch(async (reason: unknown) => {
        if (!active) return;
        if (reason instanceof ApiError && reason.status === 401) {
          await getSupabaseBrowserClient().auth.signOut();
          router.replace("/login?reason=session_expired");
          return;
        }
        setError("Mirror could not load your profile. Check your connection and try again.");
      });
    return () => { active = false; };
  }, [router]);

  async function logout() {
    setError("");
    try {
      const { error: logoutError } = await getSupabaseBrowserClient().auth.signOut();
      if (logoutError) throw logoutError;
      router.replace("/login");
      router.refresh();
    } catch {
      setError("We could not sign you out. Check your connection and try again.");
    }
  }

  return (
    <main className="shell py-16 sm:py-24">
      <div className="mx-auto max-w-2xl border-t hairline pt-8">
        <p className="mono text-[10px] uppercase tracking-[0.18em] text-[var(--silver)]">Authenticated workspace</p>
        <h1 className="display mt-5 text-5xl font-semibold tracking-[-0.05em]">Welcome to Mirror</h1>
        {!profile && !error && <p role="status" className="mt-6 text-sm text-[var(--silver)]">Loading your profile…</p>}
        {profile && <p className="mt-6 text-sm text-[var(--silver)]">Signed in as {profile.full_name || profile.email}</p>}
        {error && <p role="alert" className="mt-6 border-l-2 border-red-400 pl-3 text-sm text-red-200">{error}</p>}
        <button type="button" onClick={logout} className="button-secondary mt-10"><SignOut size={18} /> Log out</button>
      </div>
    </main>
  );
}

