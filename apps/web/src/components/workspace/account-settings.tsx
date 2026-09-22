"use client";

import { ArrowRight, Check, SignOut } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { PageAlert, PageHeader, PageLoading, PageShell, Section, usePageData } from "@/components/workspace/page-shell";
import { ApiError, mirrorApi, type Onboarding, type PreferredLanguage, type Profile } from "@/lib/api";
import { settings as t } from "@/lib/copy";
import { getSupabaseBrowserClient } from "@/lib/supabase";

const LANGUAGES: Array<{ value: PreferredLanguage; label: string }> = [
  { value: "ENGLISH", label: "English" },
  { value: "HINDI", label: "Hindi" },
  { value: "KANNADA", label: "Kannada" },
  { value: "TAMIL", label: "Tamil" },
  { value: "TELUGU", label: "Telugu" },
];

const SUPPORT_EMAIL = "support@pathwisse.com";

type SettingsData = { profile: Profile; onboarding: Onboarding };

async function loadSettings(): Promise<SettingsData> {
  const [profile, onboarding] = await Promise.all([mirrorApi.me(), mirrorApi.onboarding()]);
  return { profile, onboarding };
}

export function AccountSettings() {
  const router = useRouter();
  const { state, data, error, reload, setData } = usePageData(loadSettings, t.errors.load);
  const [fullName, setFullName] = useState("");
  const [language, setLanguage] = useState<PreferredLanguage>("ENGLISH");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [saveError, setSaveError] = useState("");
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    if (!data) return;
    setFullName(data.profile.full_name || "");
    setLanguage(data.onboarding.preferred_language || "ENGLISH");
  }, [data]);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = fullName.trim();
    if (!value || !data) return;
    setSaving(true);
    setSaveError("");
    setNotice("");
    try {
      const profile = await mirrorApi.updateMe(value);
      setData({ ...data, profile });
      setNotice(t.profile.saved);
    } catch (reason) {
      setSaveError(reason instanceof ApiError ? reason.message : t.errors.save);
    } finally {
      setSaving(false);
    }
  }

  async function saveLanguage(next: PreferredLanguage) {
    if (!data) return;
    setLanguage(next);
    setSaving(true);
    setSaveError("");
    setNotice("");
    try {
      const onboarding = await mirrorApi.updateOnboarding({ preferred_language: next });
      setData({ ...data, onboarding });
      setNotice(t.interview.saved);
    } catch (reason) {
      setLanguage(data.onboarding.preferred_language || "ENGLISH");
      setSaveError(reason instanceof ApiError ? reason.message : t.errors.save);
    } finally {
      setSaving(false);
    }
  }

  async function signOut() {
    setSigningOut(true);
    const { error: failure } = await getSupabaseBrowserClient().auth.signOut();
    if (failure) {
      setSigningOut(false);
      setSaveError(t.errors.save);
      return;
    }
    router.replace("/login");
    router.refresh();
  }

  return (
    <PageShell>
      <PageHeader eyebrow={t.eyebrow} title={t.title} intro={t.intro} />

      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}

      {state === "ready" && data ? (
        <div className="dh-home-sections">
          {notice ? (
            <p className="dh-notice" role="status">
              <Check size={16} aria-hidden="true" /> {notice}
            </p>
          ) : null}
          {saveError ? <PageAlert message={saveError} /> : null}

          <Section id="profile" label={t.profile.title} title={t.profile.title} body={t.profile.body}>
            <form className="dh-form" onSubmit={saveProfile} aria-busy={saving}>
              <label>
                <span>{t.profile.name}</span>
                <input
                  className="field"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  disabled={saving}
                  required
                  maxLength={120}
                />
              </label>
              <label>
                <span>{t.profile.email}</span>
                <input className="field" value={data.profile.email} disabled readOnly />
              </label>
              <button className="dh-primary-action" type="submit" disabled={saving || !fullName.trim()}>
                {saving ? t.profile.saving : t.profile.save}
              </button>
            </form>
          </Section>

          <Section id="interview" label={t.interview.title} title={t.interview.title} body={t.interview.body}>
            <div className="dh-form">
              <label>
                <span>{t.interview.language}</span>
                <select
                  className="field"
                  value={language}
                  onChange={(event) => void saveLanguage(event.target.value as PreferredLanguage)}
                  disabled={saving}
                >
                  {LANGUAGES.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <small>{t.interview.languageNote}</small>
              </label>
              <div className="dh-static-field">
                <span>{t.interview.mode}</span>
                <strong>{t.interview.modeValue}</strong>
                <small>{t.interview.modeNote}</small>
              </div>
            </div>
          </Section>

          <Section id="privacy" label={t.privacy.title} title={t.privacy.title} body={t.privacy.body}>
            <ul className="dh-row-list">
              <li>
                <span className="dh-row-main">
                  <strong>{t.privacy.experience}</strong>
                  <small>{t.privacy.experienceBody}</small>
                </span>
                <Link className="dh-text-action" href="/experience">
                  {t.privacy.experience} <ArrowRight size={15} aria-hidden="true" />
                </Link>
              </li>
              <li>
                <span className="dh-row-main">
                  <strong>{t.privacy.history}</strong>
                  <small>{t.privacy.historyBody}</small>
                </span>
                <Link className="dh-text-action" href="/practice">
                  {t.privacy.history} <ArrowRight size={15} aria-hidden="true" />
                </Link>
              </li>
            </ul>
            <p className="dh-fine-print">{t.privacy.note}</p>
            <div className="dh-static-field">
              <span>{t.privacy.deletion}</span>
              <small>{t.privacy.deletionBody}</small>
              <a className="dh-text-action" href={`mailto:${SUPPORT_EMAIL}`}>
                {t.privacy.deletionAction} <ArrowRight size={15} aria-hidden="true" />
              </a>
            </div>
          </Section>

          <Section id="notifications" label={t.notifications.title} title={t.notifications.title}>
            <p className="dh-prose">{t.notifications.body}</p>
          </Section>

          <Section id="account" label={t.account.title} title={t.account.title} body={t.account.body}>
            <div className="dh-action-row">
              <button className="dh-primary-action is-quiet" type="button" onClick={() => void signOut()} disabled={signingOut}>
                <SignOut size={16} aria-hidden="true" /> {signingOut ? t.account.signingOut : t.account.signOut}
              </button>
            </div>
          </Section>
        </div>
      ) : null}
    </PageShell>
  );
}
