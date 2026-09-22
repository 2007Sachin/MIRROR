import { ArrowRight, Check, Circle } from "@phosphor-icons/react";
import Link from "next/link";
import type { ReactNode } from "react";

import type { DashboardDiagnostic } from "@/lib/api";
import { home } from "@/lib/copy";
import { formatDay, type DevelopmentArea, reviewHref } from "@/lib/dashboard-view";

export function DashboardHeader({
  firstName,
  greeting,
  action,
}: {
  firstName: string;
  greeting: string;
  action: ReactNode;
}) {
  return (
    <header className="dh-header">
      <div>
        <h1 className="dh-title display">{greeting}, {firstName}</h1>
        <p>{home.title}</p>
      </div>
      {action}
    </header>
  );
}

export function NextAction({
  title,
  body,
  role,
  meta,
  supporting,
  children,
}: {
  title: string;
  body: string;
  role?: string;
  meta?: string;
  supporting?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section className="dh-next-action" aria-labelledby="dh-next-action-title">
      <p className="dh-section-label">{home.next.title}</p>
      {role ? <p className="dh-next-role">{role}</p> : null}
      <h2 id="dh-next-action-title" className="display">{title}</h2>
      <p className="dh-next-copy">{body}</p>
      {supporting}
      {children ? <div className="dh-action-row">{children}</div> : null}
      {meta ? <p className="dh-action-meta">{meta}</p> : null}
    </section>
  );
}

export function SetupProgress({
  steps,
}: {
  steps: Array<{ label: string; done: boolean }>;
}) {
  return (
    <ol className="dh-setup-progress" aria-label="Setup progress">
      {steps.map((step) => (
        <li key={step.label} className={step.done ? "is-done" : ""}>
          {step.done ? <Check size={17} aria-hidden="true" /> : <Circle size={15} aria-hidden="true" />}
          <span>{step.label}</span>
          <span className="sr-only">{step.done ? " complete" : " not complete"}</span>
        </li>
      ))}
    </ol>
  );
}

function AreaList({ areas, empty, clear }: { areas: DevelopmentArea[]; empty: string; clear?: boolean }) {
  if (areas.length === 0) return <p className="dh-review-empty">{empty}</p>;
  return (
    <ul className="dh-review-list">
      {areas.map((area) => (
        <li key={area.key}>
          {clear ? <Check size={17} aria-hidden="true" /> : <ArrowRight size={17} aria-hidden="true" />}
          <span>{area.label}</span>
        </li>
      ))}
    </ul>
  );
}

export function ReviewSummary({
  session,
  areas,
}: {
  session: DashboardDiagnostic;
  areas: DevelopmentArea[];
}) {
  const clear = areas.filter((area) => area.state === "Coming through clearly").slice(0, 2);
  const improve = areas.filter((area) => area.state === "Developing" || area.state === "Needs more practice").slice(0, 2);
  const unexplored = areas.find((area) => area.state === "Not explored yet");
  return (
    <section className="dh-section" aria-labelledby="dh-review-title">
      <div className="dh-section-heading">
        <div>
          <p className="dh-section-label">{home.latest.label}</p>
          <h2 id="dh-review-title" className="display">{session.target_role}</h2>
          <time dateTime={session.completed_at || session.updated_at}>{formatDay(session.completed_at || session.updated_at)}</time>
        </div>
        <Link className="dh-text-action" href={reviewHref(session.id)}>
          {home.latest.read} <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </div>
      <div className="dh-review-columns">
        <div>
          <h3>{home.review.clear}</h3>
          <AreaList areas={clear} empty={home.review.noClear} clear />
        </div>
        <div>
          <h3>{home.review.improve}</h3>
          <AreaList areas={improve} empty={home.review.noImprove} />
        </div>
      </div>
      {unexplored ? (
        <p className="dh-unexplored"><strong>{home.review.unexplored}:</strong> {unexplored.note}</p>
      ) : null}
    </section>
  );
}

export function DevelopmentAreas({ areas }: { areas: DevelopmentArea[] }) {
  return (
    <section className="dh-section" aria-labelledby="dh-development-title">
      <div className="dh-section-heading">
        <div>
          <p className="dh-section-label">{home.came.title}</p>
          <h2 id="dh-development-title" className="display">Four parts of a clear interview answer</h2>
        </div>
      </div>
      <ul className="dh-development-list">
        {areas.map((area) => (
          <li key={area.key}>
            <Link href={area.href}>
              <span className="dh-development-copy">
                <strong>{area.label}</strong>
                <small>{area.note}</small>
              </span>
              <span className={`dh-development-state is-${area.state.toLocaleLowerCase().replaceAll(" ", "-")}`}>
                {area.state}
              </span>
              <ArrowRight size={16} aria-hidden="true" />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ContinuePreparing({ role, action }: { role: string; action: ReactNode }) {
  return (
    <section className="dh-continue" aria-labelledby="dh-continue-title">
      <div>
        <p className="dh-section-label">{home.continuePreparing.title}</p>
        <h2 id="dh-continue-title" className="display">{role}</h2>
      </div>
      <div className="dh-continue-actions">
        {action}
        <Link className="dh-text-action" href="/sessions/new">{home.continuePreparing.another}</Link>
      </div>
    </section>
  );
}
