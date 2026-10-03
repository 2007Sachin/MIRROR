"use client";

import "@/styles/progress.css";

import { ArrowRight, ArrowUp, CheckCircle, ChartLineUp, FileText, Plus, WarningCircle } from "@phosphor-icons/react";
import Link from "next/link";

import {
  EmptyState,
  PageAlert,
  PageHeader,
  PageLoading,
  PageShell,
  usePageData,
} from "@/components/workspace/page-shell";
import { mirrorApi, type ProgressRoleTile } from "@/lib/api";
import { progress as t } from "@/lib/copy";
import { newSessionHref } from "@/lib/dashboard-view";
import { roleProgressHref, startRoleHref, tileView, type TileLine } from "@/lib/progress-view";

function HubHeader() {
  return (
    <PageHeader
      eyebrow={t.eyebrow}
      title={t.title}
      intro={t.intro}
      action={
        <Link className="pg-button is-dark" href={newSessionHref()}>
          <Plus size={14} aria-hidden="true" /> {t.addRole}
        </Link>
      }
    />
  );
}

/** The page's content for a list of roles. Shared by the real page and the local QA preview. */
export function ProgressHubView({ roles }: { roles: ProgressRoleTile[] }) {
  return (
    <>
      <HubHeader />
      {roles.length ? (
        <ul className="pg-tiles">
          {roles.map((tile) => (
            <li key={tile.role_profile_id}>
              <RoleTileCard tile={tile} />
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState title={t.hub.empty.title} body={t.hub.empty.body} action={{ href: newSessionHref(), label: t.hub.empty.action }} />
      )}
    </>
  );
}

export function ProgressHub() {
  const { state, data, error, reload } = usePageData(() => mirrorApi.progressHub(), t.errors.load);

  return (
    <PageShell>
      {state === "ready" && data ? <ProgressHubView roles={data.roles} /> : <HubHeader />}
      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}
    </PageShell>
  );
}

export function RoleTileCard({ tile }: { tile: ProgressRoleTile }) {
  const view = tileView(tile);
  const titleId = `tile-${tile.role_profile_id}`;
  const head = (
    <header className="pg-tile-head">
      <span className="pg-tile-icon" aria-hidden="true">
        {tile.stage === "NONE" ? <FileText size={20} /> : <ChartLineUp size={20} />}
      </span>
      <div>
        <h2 id={titleId}>{tile.target_role}</h2>
        <p>{view.meta}</p>
      </div>
    </header>
  );

  if (tile.stage === "NONE") {
    return (
      <article className="pg-tile is-empty" aria-labelledby={titleId}>
        {head}
        <p className="pg-tile-empty">{t.hub.noneBody}</p>
        <Link className="pg-button is-dark" href={startRoleHref(tile.target_role, tile.role_profile_id)}>
          {t.hub.start} <ArrowRight size={14} aria-hidden="true" />
        </Link>
      </article>
    );
  }

  return (
    <Link className="pg-tile" href={roleProgressHref(tile.role_profile_id)} aria-labelledby={titleId}>
      {head}
      {view.stage === "BASELINE" ? <p className="pg-baseline">{t.hub.baseline}</p> : null}
      {view.lines.map((line) => (
        <TileSignal key={line.tone} line={line} improving={tile.positive?.kind === "IMPROVING"} />
      ))}
      <span className="pg-tile-cta">
        {t.hub.view} <ArrowRight size={14} aria-hidden="true" />
      </span>
    </Link>
  );
}

function TileSignal({ line, improving }: { line: TileLine; improving: boolean }) {
  const Icon = line.tone === "attention" ? WarningCircle : improving ? ArrowUp : CheckCircle;
  return (
    <p className={`pg-signal is-${line.tone}`}>
      <Icon size={20} weight={line.tone === "attention" ? "fill" : "regular"} aria-hidden="true" />
      <span>
        <strong>{line.heading}</strong>
        <small>{line.area}</small>
      </span>
    </p>
  );
}
