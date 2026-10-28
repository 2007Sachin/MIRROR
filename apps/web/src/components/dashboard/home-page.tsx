"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { HomeView } from "@/components/dashboard/home-parts";
import { Loader } from "@/components/loader";
import { AppShell } from "@/components/workspace/app-shell";
import { useProfile } from "@/components/workspace/page-shell";
import { ApiError, mirrorApi, type HomeResponse } from "@/lib/api";
import { homeNow as t, loading } from "@/lib/copy";
import { firstNameOf, greetingForHour } from "@/lib/dashboard-view";

const POLL_DELAYS = [3000, 3000, 5000, 5000, 8000, 8000, 12000, 15000] as const;
const MAX_POLLS = 40;

type Outcome = { kind: "data"; data: HomeResponse } | { kind: "unknown-role" } | { kind: "failed" } | { kind: "gone" };

/**
 * Home, from one request. The role is a view choice kept in the address (`?role=`); the
 * server checks it belongs to this person. Until the server has answered nothing is shown
 * but the loading state, so a wrong state never flashes, and a failed load is an error,
 * never an empty Home.
 *
 * One effect owns loading and polling for the current role. Its own `cancelled` flag ends
 * it the moment the role changes or the page closes, so a slow answer for a role the
 * person has left can never overwrite the one they are looking at.
 */
export function HomePage({ initialRole }: { initialRole?: string }) {
  const router = useRouter();
  const [role, setRole] = useState<string | undefined>(initialRole);
  const [reload, setReload] = useState(0);
  const [data, setData] = useState<HomeResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const profile = useProfile();

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let polls = 0;

    async function fetchHome(): Promise<Outcome> {
      for (let attempt = 0; attempt < 3; attempt += 1) {
        try {
          const next = await mirrorApi.home(role);
          return cancelled ? { kind: "gone" } : { kind: "data", data: next };
        } catch (reason) {
          if (cancelled) return { kind: "gone" };
          if (reason instanceof ApiError && reason.status === 401) {
            router.replace("/login?reason=session_expired");
            return { kind: "gone" };
          }
          if (reason instanceof ApiError && reason.status === 404 && role) return { kind: "unknown-role" };
          const transient = reason instanceof ApiError && (reason.status === 0 || reason.status === 502 || reason.status === 503);
          if (transient && attempt < 2) {
            await new Promise((resolve) => setTimeout(resolve, 500 * (attempt + 1)));
            if (cancelled) return { kind: "gone" };
            continue;
          }
          return { kind: "failed" };
        }
      }
      return { kind: "failed" };
    }

    async function run() {
      const outcome = await fetchHome();
      if (cancelled || outcome.kind === "gone") return;
      if (outcome.kind === "unknown-role") {
        // Not one of this person's roles: fall back to their own and clean the address.
        window.history.replaceState(null, "", "/dashboard");
        setRole(undefined);
        return;
      }
      if (outcome.kind === "failed") {
        setFailed(true);
        return;
      }
      setFailed(false);
      setData(outcome.data);
      if (outcome.data.state !== "REVIEW_PROCESSING" || polls >= MAX_POLLS) return;
      timer = setTimeout(() => void run(), POLL_DELAYS[Math.min(polls, POLL_DELAYS.length - 1)]);
      polls += 1;
    }

    void run();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [role, reload, router]);

  function selectRole(roleProfileId: string) {
    setData(null); // nothing of the previous role stays on screen while the new one loads
    setFailed(false);
    setRole(roleProfileId);
    window.history.replaceState(null, "", `/dashboard?role=${encodeURIComponent(roleProfileId)}`);
  }

  async function end(sessionId: string) {
    await mirrorApi.endInterview(sessionId);
    setReload((count) => count + 1); // the same effect loads again and starts polling for the review
  }

  async function retry(sessionId: string) {
    await mirrorApi.retryAssessment(sessionId);
    setReload((count) => count + 1);
  }

  return (
    <AppShell profile={profile}>
      <div className="dh">
        {!data && !failed ? <Loader label={loading.space.label} note={loading.space.note} /> : null}
        {failed ? (
          <div className="dh-alert" role="alert">
            <span>{t.errors.load}</span>
            <button
              type="button"
              onClick={() => {
                setFailed(false);
                setReload((count) => count + 1);
              }}
            >
              {t.errors.reload}
            </button>
          </div>
        ) : null}
        {data && !failed ? (
          <HomeView
            data={data}
            greeting={greetingForHour(new Date().getHours())}
            firstName={firstNameOf(profile?.full_name, profile?.email)}
            handlers={{ onSelectRole: selectRole, onEnd: end, onRetry: retry }}
          />
        ) : null}
      </div>
    </AppShell>
  );
}
