"use client";

import "@/styles/auth.css";

import { ArrowRight, GoogleLogo } from "@phosphor-icons/react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";
import { getSupabaseBrowserClient, isSupabaseConfigured } from "@/lib/supabase";

const AnimatedEnergyMesh = dynamic(
  () => import("@/components/auth/animated-energy-mesh").then((module) => module.AnimatedEnergyMesh),
  { ssr: false, loading: () => <div className="mirror-mesh" aria-hidden="true" /> },
);

type Mode = "login" | "signup";

function friendlyAuthError(code?: string) {
  switch (code) {
    case "invalid_credentials":
    case "email_not_confirmed":
      return "That email and password didn't match, or the email isn't confirmed yet. Please try again.";
    case "user_already_exists":
      return "There's already an account with this email. You can sign in instead.";
    case "weak_password":
      return "Please choose a password with at least eight characters.";
    case "over_email_send_rate_limit":
      return "That was a few too many tries. Please wait a few minutes and try again.";
    case "signup_disabled":
      return "New accounts can't be created right now. Please try again later.";
    default:
      return "We couldn't sign you in just now. Please check your details and try again.";
  }
}

export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [busy, setBusy] = useState(false);
  const reason = searchParams.get("reason");
  const [error, setError] = useState(
    searchParams.get("error") === "oauth"
      ? "We couldn't finish signing you in with Google. Please try again."
      : reason === "configuration"
        ? "Authentication is not configured for this environment."
        : reason === "network"
          ? "We couldn't reach the sign-in service just now. Please check your connection and try again."
      : reason === "session_expired"
        ? "Your session has ended. Please sign in again."
        : "",
  );
  const [notice, setNotice] = useState("");
  const [formFocused, setFormFocused] = useState(false);
  const configured = isSupabaseConfigured();
  const googleEnabled = process.env.NEXT_PUBLIC_GOOGLE_OAUTH_ENABLED === "true";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!configured) {
      setError("Authentication is not configured for this environment.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");

    try {
      const client = getSupabaseBrowserClient();
      const result = mode === "login"
        ? await client.auth.signInWithPassword({ email, password })
        : await client.auth.signUp({
            email,
            password,
            options: { data: { full_name: String(form.get("full_name") ?? "").trim() } },
          });

      if (result.error) {
        setError(friendlyAuthError(result.error.code));
        return;
      }
      if (mode === "signup" && !result.data.session) {
        setNotice("Please check your email to confirm your account, then come back here to sign in.");
        return;
      }
      router.replace("/dashboard");
      router.refresh();
    } catch {
      setError("We couldn't reach the sign-in service just now. Please check your connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  async function signInWithGoogle() {
    if (!configured) return setError("Authentication is not configured for this environment.");
    setBusy(true);
    setError("");
    try {
      const { error: oauthError } = await getSupabaseBrowserClient().auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo: `${window.location.origin}/auth/callback?next=/dashboard` },
      });
      if (oauthError) setError(friendlyAuthError(oauthError.code));
    } catch {
      setError("We couldn't reach Google just now. Please check your connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  const isLogin = mode === "login";
  return (
    <main id="main-content" className="mirror-auth">
      <section className="mirror-auth-visual" aria-hidden="true">
        <div className="mirror-auth-visual-inner">
          <p className="mirror-auth-visual-eyebrow">Mirror by Pathwisse</p>
          <AnimatedEnergyMesh energized={formFocused || busy} />
          <p className="mirror-auth-visual-copy">Find the words for your experience.</p>
        </div>
      </section>
      <section className="mirror-auth-panel">
        <div className="mirror-auth-panel-inner fade-in-once">
          <p className="mirror-auth-eyebrow">Your private space</p>
          <h1 className="display mirror-auth-title">
            {isLogin ? "Sign in to Mirror" : "Create your account"}
          </h1>
          <p className="mirror-auth-intro">
            {isLogin
              ? "Pick up your practice where you left off."
              : "Start a private, gentle practice session."}
          </p>
          <form
            onSubmit={submit}
            className="mirror-auth-form"
            onFocusCapture={() => setFormFocused(true)}
            onBlurCapture={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFormFocused(false);
            }}
          >
            {!isLogin && (
              <label className="mirror-auth-field">
                <span>Full name</span>
                <input className="field" name="full_name" required maxLength={120} autoComplete="name" disabled={busy} />
              </label>
            )}
            <label className="mirror-auth-field">
              <span>Email</span>
              <input className="field" name="email" type="email" required autoComplete="email" disabled={busy} />
            </label>
            <label className="mirror-auth-field">
              <span>Password</span>
              <input className="field" name="password" type="password" required minLength={8} autoComplete={isLogin ? "current-password" : "new-password"} disabled={busy} />
            </label>
            {error && <p role="alert" className="mirror-auth-message">{error}</p>}
            {notice && <p role="status" className="mirror-auth-message is-notice">{notice}</p>}
            <div className="mirror-auth-submit-row">
              <button type="submit" className="button-primary w-full" disabled={busy || !configured}>
                {busy ? "Please wait…" : isLogin ? "Sign in" : "Create account"}
                {!busy && <ArrowRight size={18} />}
                {busy && (
                  <svg className="mirror-auth-spinner" width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                    <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeOpacity="0.3" strokeWidth="2" />
                    <path d="M14.5 8a6.5 6.5 0 0 0-6.5-6.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                )}
              </button>
            </div>
          </form>
          {googleEnabled && (
            <>
              <div className="mirror-auth-divider">or</div>
              <button type="button" className="button-secondary w-full" onClick={signInWithGoogle} disabled={busy || !configured}>
                <GoogleLogo size={18} /> Continue with Google
              </button>
            </>
          )}
          <p className="mirror-auth-switch">
            {isLogin ? "New to Mirror? " : "Already have an account? "}
            <Link href={isLogin ? "/signup" : "/login"}>
              {isLogin ? "Create an account" : "Sign in"}
            </Link>
          </p>
          {!configured && <p className="mirror-auth-config-note">Set the public Supabase URL and publishable/anonymous key to enable authentication.</p>}
        </div>
      </section>
    </main>
  );
}
