"use client";

import "@/styles/home.css";

import { ArrowRight, CalendarBlank, CaretDown, ChartBar, FileText, Target } from "@phosphor-icons/react";
import Link from "next/link";
import { useRef, useState, type ReactNode } from "react";

import type { HomeActivePractice, HomeResponse, HomeUpcomingInterview } from "@/lib/api";
import { homeNow as t } from "@/lib/copy";
import { newSessionHref, reviewHref } from "@/lib/dashboard-view";
import {
  activityRow,
  answersHref,
  briefHref,
  continueHref,
  practiceArea,
  practiceHeading,
  recommendedTitle,
  startStepHref,
  subline,
  timeAgo,
  upcomingLine,
  whyHref,
} from "@/lib/home-view";
import { areaLabel, insightViews, roleProgressHref, startRoleHref } from "@/lib/progress-view";

export type HomeHandlers = {
  onSelectRole: (roleProfileId: string) => void;
  onEnd: (sessionId: string) => Promise<void>;
  onRetry: (sessionId: string) => Promise<void>;
};

/** The whole page for one server decision. Shared by the real page and the local QA preview. */
export function HomeView({
  data,
  greeting,
  firstName,
  handlers,
  now = new Date(),
}: {
  data: HomeResponse;
  greeting: string;
  firstName: string;
  handlers: HomeHandlers;
  now?: Date;
}) {
  const role = data.selected;
  const roleId = role?.role_profile_id ?? "";
  const comparable = data.progress?.stage === "COMPARABLE" && data.progress.insights.length > 0;
  const showSince = comparable && !["FIRST_PRACTICE", "EARLY_BASELINE", "NO_ROLE"].includes(data.state);
  const showUpNext = data.next_step && (data.state === "ACTIVE_PRACTICE" || data.state === "REVIEW_READY");

  return (
    <div className="hm">
      <header className="hm-header">
        <h1 className="dh-title display">{greeting}, {firstName}</h1>
        <p className="hm-sub">{subline(data)}</p>
        {role ? <RoleContext data={data} onSelect={handlers.onSelectRole} /> : null}
      </header>

      <div className="hm-stack">
        {data.upcoming_interview ? <UpcomingInterview event={data.upcoming_interview} now={now} /> : null}
        {data.other_active ? <OtherRole practice={data.other_active} onEnd={handlers.onEnd} now={now} /> : null}
        <Primary data={data} handlers={handlers} now={now} />
        {data.state === "EARLY_BASELINE" ? <Focus data={data} /> : null}
        {showUpNext ? <UpNext data={data} /> : null}
        {showSince && role ? <Since data={data} roleId={roleId} roleName={role.target_role} /> : null}
        {role ? <Preparation data={data} roleId={roleId} roleName={role.target_role} /> : null}
        {data.activity.length ? <Activity data={data} now={now} /> : null}
      </div>
    </div>
  );
}

function RoleContext({ data, onSelect }: { data: HomeResponse; onSelect: (id: string) => void }) {
  const selected = data.selected;
  if (!selected) return null;
  if (data.roles.length < 2) {
    return <p className="hm-role">{t.preparingFor} <strong>{selected.target_role}</strong></p>;
  }
  return (
    <label className="hm-role">
      <span>{t.preparingFor}</span>
      <span className="hm-select">
        <select value={selected.role_profile_id} onChange={(event) => onSelect(event.target.value)} aria-label={t.roleLabel}>
          {data.roles.map((option) => (
            <option key={option.role_profile_id} value={option.role_profile_id}>{option.target_role}</option>
          ))}
        </select>
        <CaretDown size={13} aria-hidden="true" />
      </span>
    </label>
  );
}

function Card({
  eyebrow,
  tone,
  children,
  icon,
  badge,
  label,
}: {
  eyebrow: string;
  tone?: "attention";
  children: ReactNode;
  icon?: ReactNode;
  badge?: string;
  label: string;
}) {
  return (
    <section className={`hm-card${tone ? ` is-${tone}` : ""}`} aria-labelledby={label}>
      <div className="hm-card-main">
        <div className="hm-eyebrow-row">
          <p className="dh-section-label">{eyebrow}</p>
          {badge ? <span className="hm-badge">{badge}</span> : null}
        </div>
        {children}
      </div>
      {icon ? <span className="hm-card-icon" aria-hidden="true">{icon}</span> : null}
    </section>
  );
}

function practiceModeTitle(mode: string) {
  return mode === "FOCUSED_PRACTICE" ? "Focused practice" : mode === "QUICK_DRILL" ? "Quick drill" : "Practice";
}

function Primary({ data, handlers, now }: { data: HomeResponse; handlers: HomeHandlers; now: Date }) {
  const role = data.selected;
  const name = role?.target_role ?? "";
  const step = data.next_step;

  if (data.state === "NO_ROLE") {
    return (
      <Card eyebrow={t.noRole.title} label="hm-primary">
        <h2 id="hm-primary" className="hm-title">{t.noRole.title}</h2>
        <p className="hm-body">{t.noRole.body}</p>
        <div className="hm-actions">
          <Link className="hm-primary-action" href={newSessionHref()}>{t.noRole.cta} <ArrowRight size={16} aria-hidden="true" /></Link>
        </div>
      </Card>
    );
  }
  if (data.state === "ACTIVE_PRACTICE" && data.active) {
    return <ActiveCard practice={data.active} onEnd={handlers.onEnd} now={now} />;
  }
  if (data.review && (data.state === "REVIEW_READY" || data.state === "REVIEW_PROCESSING" || data.state === "REVIEW_FAILED")) {
    const review = data.review;
    const heading = practiceHeading(review.target_role, review.practice_mode);
    if (data.state === "REVIEW_READY") {
      return (
        <Card eyebrow={t.review.eyebrow} label="hm-primary" icon={<FileText size={34} />}>
          <h2 id="hm-primary" className="hm-title">{heading}</h2>
          <p className="hm-meta">{t.review.completed(review.question_count, timeAgo(review.finished_at, now))}</p>
          <p className="hm-body">{t.review.body}</p>
          <div className="hm-actions">
            <Link className="hm-primary-action" href={reviewHref(review.session_id)}>{t.review.view} <ArrowRight size={16} aria-hidden="true" /></Link>
          </div>
        </Card>
      );
    }
    if (data.state === "REVIEW_PROCESSING") {
      return (
        <Card eyebrow={t.review.processingEyebrow} label="hm-primary">
          <h2 id="hm-primary" className="hm-title">{heading}</h2>
          <p className="hm-body" role="status">{t.review.processingBody}</p>
        </Card>
      );
    }
    return <FailedReview heading={heading} sessionId={review.session_id} onRetry={handlers.onRetry} />;
  }
  if (data.state === "FIRST_PRACTICE" && role) {
    return (
      <Card eyebrow={t.first.eyebrow} label="hm-primary" icon={<FileText size={34} />}>
        <h2 id="hm-primary" className="hm-title">{t.first.title(name)}</h2>
        <p className="hm-body">{t.first.body}</p>
        <div className="hm-actions">
          <Link className="hm-primary-action" href={startRoleHref(name, role.role_profile_id)}>{t.first.cta(name)} <ArrowRight size={16} aria-hidden="true" /></Link>
        </div>
      </Card>
    );
  }
  if (data.state === "EARLY_BASELINE" && role) {
    return (
      <Card eyebrow={t.early.eyebrow} label="hm-primary" icon={<ChartBar size={34} />}>
        <h2 id="hm-primary" className="hm-title">{t.early.title(name)}</h2>
        <p className="hm-body">{t.early.body}</p>
        <div className="hm-actions">
          <Link className="hm-primary-action" href={startRoleHref(name, role.role_profile_id)}>{t.early.cta} <ArrowRight size={16} aria-hidden="true" /></Link>
        </div>
      </Card>
    );
  }
  if (data.state === "RECOMMENDED_NEXT" && step) {
    return (
      <Card eyebrow={t.recommended.eyebrow} label="hm-primary" icon={<Target size={34} />}>
        <h2 id="hm-primary" className="hm-title">{recommendedTitle(step)}</h2>
        <p className="hm-body">{step.reason}</p>
        <div className="hm-actions">
          <Link className="hm-primary-action" href={startStepHref(step)}>
            {t.recommended.start(practiceModeTitle(step.mode))} <ArrowRight size={16} aria-hidden="true" />
          </Link>
          <Link className="hm-text-action" href={answersHref(step)}>{t.recommended.seeWhy} <ArrowRight size={15} aria-hidden="true" /></Link>
        </div>
      </Card>
    );
  }
  return (
    <Card eyebrow={t.returning.eyebrow} label="hm-primary" icon={<Target size={34} />}>
      <h2 id="hm-primary" className="hm-title">{t.returning.title(name)}</h2>
      <p className="hm-body">{t.returning.body}</p>
      <div className="hm-actions">
        {role ? (
          <Link className="hm-primary-action" href={startRoleHref(name, role.role_profile_id)}>{t.returning.cta} <ArrowRight size={16} aria-hidden="true" /></Link>
        ) : null}
      </div>
    </Card>
  );
}

function questionLine(practice: HomeActivePractice) {
  const total = practice.question_total;
  const number = practice.question_number;
  if (practice.kind !== "ACTIVE" || number === 0) return t.active.notStarted;
  return total ? t.active.question(Math.min(number, total), total) : t.active.questionsSoFar(number);
}

function ActiveCard({ practice, onEnd, now }: { practice: HomeActivePractice; onEnd: HomeHandlers["onEnd"]; now: Date }) {
  const started = practice.kind === "ACTIVE";
  const area = practiceArea(practice.practice_mode, practice.practice_focus, practice.practice_theme);
  const total = practice.question_total;
  const number = practice.question_number;
  return (
    <Card eyebrow={started ? t.active.eyebrow : t.active.readyEyebrow} badge={started ? t.active.badge : undefined} label="hm-primary">
      <h2 id="hm-primary" className="hm-title">{practiceHeading(practice.target_role, practice.practice_mode)}</h2>
      {area ? <p className="hm-meta">{area}</p> : null}
      <div className="hm-progress-row">
        <span className="hm-meta">{questionLine(practice)}</span>
        {started ? <span className="hm-meta">{t.active.lastActive(timeAgo(practice.last_active_at, now))}</span> : null}
      </div>
      {total && number > 0 ? (
        <progress className="hm-progress" value={Math.min(number, total)} max={total} aria-label={t.active.progressLabel(Math.min(number, total), total)} />
      ) : null}
      <div className="hm-actions">
        <Link className="hm-primary-action" href={continueHref(practice.session_id)}>
          {started ? t.active.continue : t.active.begin} <ArrowRight size={16} aria-hidden="true" />
        </Link>
        <EndPractice sessionId={practice.session_id} onEnd={onEnd} />
      </div>
    </Card>
  );
}

function EndPractice({ sessionId, onEnd }: { sessionId: string; onEnd: HomeHandlers["onEnd"] }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const group = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  // Focus follows the person: into the question when it opens, back to the button when it closes.
  function open() {
    setConfirming(true);
    requestAnimationFrame(() => group.current?.focus());
  }
  function close() {
    setConfirming(false);
    requestAnimationFrame(() => trigger.current?.focus());
  }

  async function end() {
    setBusy(true);
    setFailed(false);
    try {
      await onEnd(sessionId);
    } catch {
      setFailed(true);
      setBusy(false);
    }
  }

  if (!confirming) {
    return <button ref={trigger} type="button" className="hm-secondary-action" onClick={open}>{t.active.end}</button>;
  }
  return (
    <div ref={group} tabIndex={-1} className="hm-confirm" role="group" aria-label={t.active.endTitle}>
      <p><strong>{t.active.endTitle}</strong> {t.active.endBody}</p>
      <div className="hm-actions">
        <button type="button" className="hm-secondary-action is-strong" disabled={busy} onClick={() => void end()}>
          {busy ? t.active.ending : t.active.endConfirm}
        </button>
        <button type="button" className="hm-text-action" disabled={busy} onClick={close}>{t.active.endCancel}</button>
      </div>
      {failed ? <p className="hm-error" role="alert">{t.active.endFailed}</p> : null}
    </div>
  );
}

function FailedReview({ heading, sessionId, onRetry }: { heading: string; sessionId: string; onRetry: HomeHandlers["onRetry"] }) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  async function retry() {
    setBusy(true);
    setFailed(false);
    try {
      await onRetry(sessionId);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card eyebrow={t.review.failedEyebrow} tone="attention" label="hm-primary">
      <h2 id="hm-primary" className="hm-title">{heading}</h2>
      <p className="hm-body">{t.review.failedBody}</p>
      <div className="hm-actions">
        <button type="button" className="hm-primary-action" disabled={busy} onClick={() => void retry()}>
          {busy ? t.review.retrying : t.review.retry}
        </button>
      </div>
      {failed ? <p className="hm-error" role="alert">{t.review.retryFailed}</p> : null}
    </Card>
  );
}

function OtherRole({ practice, onEnd, now }: { practice: HomeActivePractice; onEnd: HomeHandlers["onEnd"]; now: Date }) {
  const area = practiceArea(practice.practice_mode, practice.practice_focus, practice.practice_theme);
  const line = [area, questionLine(practice), t.active.lastActive(timeAgo(practice.last_active_at, now))].filter(Boolean).join(" · ");
  return (
    <Card eyebrow={t.otherRole.eyebrow} tone="attention" label="hm-other">
      <h2 id="hm-other" className="hm-title">{practiceHeading(practice.target_role, practice.practice_mode)}</h2>
      <p className="hm-meta">{line}</p>
      <div className="hm-actions">
        <Link className="hm-primary-action" href={continueHref(practice.session_id)}>
          {t.otherRole.continue(practice.target_role)} <ArrowRight size={16} aria-hidden="true" />
        </Link>
        <EndPractice sessionId={practice.session_id} onEnd={onEnd} />
      </div>
    </Card>
  );
}

/** A quiet note above the main card: never a second headline. */
function UpcomingInterview({ event, now }: { event: HomeUpcomingInterview; now: Date }) {
  return (
    <aside className="hm-upcoming" aria-label={t.upcoming.label}>
      <CalendarBlank size={18} aria-hidden="true" />
      <p>{upcomingLine(event, now)}</p>
      <Link className="hm-text-action" href={briefHref(event)}>
        {t.upcoming.readBrief} <ArrowRight size={15} aria-hidden="true" />
      </Link>
    </aside>
  );
}

function UpNext({ data }: { data: HomeResponse }) {
  const step = data.next_step;
  if (!step) return null;
  return (
    <section className="hm-section" aria-labelledby="hm-up-next">
      <p className="dh-section-label">{t.upNext.eyebrow}</p>
      <h2 id="hm-up-next" className="hm-section-title">{recommendedTitle(step)}</h2>
      <p className="hm-body">{step.reason}</p>
      <div className="hm-actions">
        <Link className="hm-secondary-action" href={startStepHref(step)}>{t.upNext.practiceThis} <ArrowRight size={15} aria-hidden="true" /></Link>
        <Link className="hm-text-action" href={whyHref(step)}>{t.upNext.seeWhy} <ArrowRight size={15} aria-hidden="true" /></Link>
      </div>
    </section>
  );
}

function Focus({ data }: { data: HomeResponse }) {
  const step = data.next_step;
  const first = data.progress?.highlights[0];
  const roleId = data.selected?.role_profile_id ?? "";
  if (!step && !first) return null;
  const title = step ? (step.dimension ? areaLabel(step.dimension) : recommendedTitle(step)) : areaLabel(first?.dimension ?? "");
  return (
    <section className="hm-section" aria-labelledby="hm-focus">
      <p className="dh-section-label">{t.early.focusEyebrow}</p>
      <h2 id="hm-focus" className="hm-section-title">{title}</h2>
      <p className="hm-body">{step ? step.reason : first?.note}</p>
      <div className="hm-actions">
        {step ? (
          <Link className="hm-secondary-action" href={startStepHref(step)}>{t.early.practiceThis} <ArrowRight size={15} aria-hidden="true" /></Link>
        ) : null}
        <Link className="hm-text-action" href={step ? answersHref(step) : roleProgressHref(roleId, "answers")}>
          {t.early.seeAnswers} <ArrowRight size={15} aria-hidden="true" />
        </Link>
      </div>
    </section>
  );
}

function Since({ data, roleId, roleName }: { data: HomeResponse; roleId: string; roleName: string }) {
  const views = insightViews(data.progress?.insights ?? []);
  return (
    <section className="hm-section" aria-labelledby="hm-since">
      <p className="dh-section-label" id="hm-since">{t.since.eyebrow}</p>
      <ul className="hm-insights">
        {views.map((view) => (
          <li key={view.key} className={`is-${view.trend.toLowerCase()}`}>
            <strong>{view.title}</strong>
            <span>{view.body}</span>
          </li>
        ))}
      </ul>
      <Link className="hm-text-action" href={roleProgressHref(roleId)}>{t.since.view(roleName)} <ArrowRight size={15} aria-hidden="true" /></Link>
    </section>
  );
}

function Preparation({ data, roleId, roleName }: { data: HomeResponse; roleId: string; roleName: string }) {
  const map = data.map;
  const stories = data.stories;
  const count = data.progress?.practice_count ?? 0;
  const storyTotal = stories ? stories.ready + stories.developing : 0;
  const storyLine =
    stories?.state !== "READY"
      ? t.prep.stories.unavailable
      : storyTotal === 0
        ? t.prep.stories.none
        : `${t.prep.stories.ready(stories.ready)}${stories.developing ? ` ${t.prep.stories.developing(stories.developing)}` : ""}`;
  return (
    <section className="hm-section" aria-labelledby="hm-prep">
      <p className="dh-section-label" id="hm-prep">{t.prep.eyebrow}</p>
      <div className="hm-prep">
        <article className="hm-prep-card">
          <h3>{t.prep.map.title}</h3>
          <p>
            {map?.state === "READY"
              ? t.prep.map.ready(map.without_example)
              : map?.state === "PREPARING"
                ? t.prep.map.preparing
                : t.prep.map.unavailable}
          </p>
          <Link className="hm-text-action" href={`/plan?role=${encodeURIComponent(roleId)}`}>{t.prep.map.open} <ArrowRight size={15} aria-hidden="true" /></Link>
        </article>
        <article className="hm-prep-card">
          <h3>{t.prep.stories.title}</h3>
          <p>{storyLine}</p>
          <Link className="hm-text-action" href="/stories">{t.prep.stories.open} <ArrowRight size={15} aria-hidden="true" /></Link>
        </article>
        <article className="hm-prep-card">
          <h3>{t.prep.progress.title}</h3>
          <p>{count ? t.prep.progress.some(count, roleName) : t.prep.progress.none(roleName)}</p>
          {count ? (
            <Link className="hm-text-action" href={roleProgressHref(roleId)}>{t.prep.progress.open} <ArrowRight size={15} aria-hidden="true" /></Link>
          ) : (
            <Link className="hm-text-action" href={startRoleHref(roleName, roleId)}>{t.prep.progress.start} <ArrowRight size={15} aria-hidden="true" /></Link>
          )}
        </article>
      </div>
    </section>
  );
}

function Activity({ data, now }: { data: HomeResponse; now: Date }) {
  return (
    <section className="hm-section" aria-labelledby="hm-recent">
      <p className="dh-section-label" id="hm-recent">{t.recent.eyebrow}</p>
      <ul className="hm-activity">
        {data.activity.map((item) => {
          const row = activityRow(item, now);
          return (
            <li key={row.key}>
              <time className="hm-date" dateTime={row.at}>{row.date}</time>
              <span className="hm-activity-text">{row.text}</span>
              <Link className="hm-text-action" href={row.href}>{row.action} <ArrowRight size={14} aria-hidden="true" /></Link>
            </li>
          );
        })}
      </ul>
      <Link className="hm-text-action" href="/practice">{t.recent.all} <ArrowRight size={15} aria-hidden="true" /></Link>
    </section>
  );
}
