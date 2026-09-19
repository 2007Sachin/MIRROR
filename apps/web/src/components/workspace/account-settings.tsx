"use client";

import { Check, WarningCircle } from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/workspace/app-shell";
import { Reveal } from "@/components/motion/reveal";
import { ApiError, mirrorApi, type Profile } from "@/lib/api";

export function AccountSettings() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [fullName, setFullName] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const nextProfile = await mirrorApi.me();
      setProfile(nextProfile);
      setFullName(nextProfile.full_name || "");
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) {
        router.replace("/login?reason=session_expired");
        return;
      }
      setError("Mirror could not load your account details.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = fullName.trim();
    if (!value) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const nextProfile = await mirrorApi.updateMe(value);
      setProfile(nextProfile);
      setFullName(nextProfile.full_name || "");
      setMessage("Your profile has been updated.");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Mirror could not update your profile.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell profile={profile}>
      <header className="ws-page-header is-stacked">
        <div><p className="ws-eyebrow">Settings</p><h1 className="display">Your account</h1><p>Manage the profile information attached to your private evidence workspace.</p></div>
      </header>

      {error ? <div className="ws-alert is-inline" role="alert"><WarningCircle size={18} /><span>{error}</span><button type="button" onClick={() => void load()}>Retry</button></div> : null}
      {message ? <div className="ws-success" role="status"><Check size={17} />{message}</div> : null}

      <Reveal>
        <section className="ws-panel" aria-labelledby="profile-settings-title">
          <div className="ws-section-heading is-flush"><div><p className="ws-eyebrow">Profile</p><h2 id="profile-settings-title">Account details</h2><p>This name appears in your Mirror workspace. Your sign-in email is managed by your authentication account.</p></div></div>
          <form className="ws-form" onSubmit={submit} aria-busy={saving || loading}>
            <label><span>Full name</span><input className="field" value={fullName} onChange={(event) => setFullName(event.target.value)} disabled={loading || saving} required maxLength={120} /></label>
            <label><span>Email address</span><input className="field" value={profile?.email || ""} disabled readOnly /></label>
            <button className="button-primary" type="submit" disabled={loading || saving || !fullName.trim()}>{saving ? "Saving..." : "Save changes"}</button>
          </form>
        </section>
      </Reveal>
    </AppShell>
  );
}
