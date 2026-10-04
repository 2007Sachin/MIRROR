"use client";

import "@/styles/plan.css";

import { ArrowLeft, ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageAlert, PageHeader, PageLoading, PageShell } from "@/components/workspace/page-shell";
import { ApiError } from "@/lib/api";
import { getRound, targetForRole, type RoundDetail, type TargetView } from "@/lib/api-targets";
import {
  cannotDo,
  claimCopy,
  claimMatchesTargetScope,
  competencyLabel,
  conflictCopy,
  countryLabel,
  failureKind,
  planHref,
  reasonLabel,
  roundCovers,
  roundLabel,
  roundPracticeHref,
  shortDate,
  sourceLabel,
  targetCopy,
  targetLine,
  unknownCopy,
} from "@/lib/copy-targets";
import { planCopy } from "@/lib/copy-plan";

const t = targetCopy.round;

type RoundState =
  | { kind: "loading" }
  | { kind: "no-target" }
  | { kind: "unavailable" }
  | { kind: "not-found" }
  | { kind: "error" }
  | { kind: "ready"; target: TargetView; detail: RoundDetail };

async function loadRound(roleProfileId: string, roundKey: string): Promise<RoundState> {
  const found = await targetForRole(roleProfileId).catch(() => ({ kind: "UNAVAILABLE" as const }));
  if (found.kind === "UNAVAILABLE") return { kind: "unavailable" };
  if (found.kind === "NONE") return { kind: "no-target" };
  try {
    const detail = await getRound(found.target.id, roundKey);
    if (detail.availability !== "AVAILABLE" || !detail.round) return { kind: "unavailable" };
    return { kind: "ready", target: found.target, detail };
  } catch (reason) {
    if (reason instanceof ApiError && reason.status === 404) return { kind: "not-found" };
    if (reason instanceof ApiError && failureKind(reason.status) === "UNAVAILABLE") return { kind: "unavailable" };
    return { kind: "error" };
  }
}

/** One practice round for one role's interview target: what it covers, what Mirror can do, practice. */
export function RoundPage({ roleProfileId, roundKey }: { roleProfileId: string; roundKey: string }) {
  const [state, setState] = useState<RoundState>({ kind: "loading" });
  const heading = useRef<HTMLHeadingElement>(null);

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    setState(await loadRound(roleProfileId, roundKey));
  }, [roleProfileId, roundKey]);

  useEffect(() => {
    void load();
  }, [load]);

  // Focus lands on the round's name once it is there, so keyboard and screen readers start at the top.
  useEffect(() => {
    if (state.kind === "ready") heading.current?.focus();
  }, [state.kind]);

  const back = { href: planHref(roleProfileId), label: t.back };
  const title = roundLabel(roundKey) ?? t.notFoundTitle;

  return (
    <PageShell>
      {state.kind === "ready" ? (
        <header className="dh-page-header">
          <Link className="dh-back-link" href={`${back.href}#round-${roundKey}`}>
            <ArrowLeft size={15} aria-hidden="true" /> {back.label}
          </Link>
          <p className="dh-section-label">{planCopy.eyebrow}</p>
          <h1 className="dh-title display" ref={heading} tabIndex={-1}>{title}</h1>
          <p className="pl-target-line">{targetLine(state.target)}</p>
        </header>
      ) : (
        <PageHeader eyebrow={planCopy.eyebrow} title={state.kind === "not-found" ? t.notFoundTitle : title} back={back} />
      )}
      {state.kind === "loading" ? <PageLoading /> : null}
      {state.kind === "error" ? <PageAlert message={t.loadError} onRetry={() => void load()} /> : null}
      {state.kind === "not-found" ? (
        <section className="dh-empty">
          <p>{t.notFoundBody}</p>
          <Link className="dh-text-action" href={back.href}>{t.backToPlan} <ArrowRight size={15} aria-hidden="true" /></Link>
        </section>
      ) : null}
      {state.kind === "unavailable" ? <p className="pl-quiet">{targetCopy.section.unavailable}</p> : null}
      {state.kind === "no-target" ? <p className="pl-quiet">{t.noTarget}</p> : null}
      {state.kind === "ready" ? <RoundBody target={state.target} detail={state.detail} roleProfileId={roleProfileId} /> : null}
    </PageShell>
  );
}

function RoundBody({ target, detail, roleProfileId }: { target: TargetView; detail: RoundDetail; roleProfileId: string }) {
  const round = detail.round!;
  const claims = detail.claims.filter((claim) => claimMatchesTargetScope(claim, target) && claimCopy(claim.key));
  const conflicts = detail.conflicts.filter((conflict) => conflictCopy(conflict.key) && conflict.claims.some((claim) => claimMatchesTargetScope(claim, target) && claimCopy(claim.key)));
  const unknowns = detail.unknowns.filter((unknown) => unknownCopy(unknown.key));
  const researched = detail.match_state === "RESEARCHED" || detail.match_state === "GENERAL_ONLY";
  const pack = detail.pack;
  const canPractise = pack?.state === "FULL" && pack.prompts.length > 0;
  const history = detail.practice ?? { count: 0, sessions: [] };
  const amazon = target.company_key === "amazon";

  return (
    <div className="pl-round">
      <section aria-labelledby="round-covers">
        <h2 id="round-covers" className="pl-run-title">{t.coversTitle}</h2>
        <p>{roundCovers(round.label_key)}</p>
        {researched && claims.length ? (
          <ul className="pl-stages">
            {claims.map((claim) => (
              <li key={claim.key}>
                <p>{claimCopy(claim.key)}</p>
                <p className="pl-source">{sourceLabel(claim, target.company_label)}</p>
              </li>
            ))}
          </ul>
        ) : (
          <>
            <p className="pl-quiet">
              {detail.match_state === "NOT_RESEARCHED" && target.company_key
                ? targetCopy.section.notYetResearched(target.company_label, countryLabel(target))
                : t.coversSuggested}
            </p>
            <ul className="pl-plain">
              {round.competency_keys.map((key) => competencyLabel(key)).filter(Boolean).map((label) => (
                <li key={label}>
                  {label} <span className="pl-source">· {targetCopy.basis.MIRROR_SUGGESTED}</span>
                </li>
              ))}
            </ul>
          </>
        )}
        {researched && conflicts.length
          ? conflicts.map((conflict) => (
              <div key={conflict.key} className="pl-conflict">
                <p className="pl-state-title">{targetCopy.section.conflictTitle}</p>
                <p>{conflictCopy(conflict.key)}</p>
                <ul className="pl-conflict-sides">
                  {conflict.claims.filter((claim) => claimMatchesTargetScope(claim, target) && claimCopy(claim.key)).map((claim) => (
                    <li key={claim.key}>
                      <p>{claimCopy(claim.key)}</p>
                      <p className="pl-source">{sourceLabel(claim, target.company_label)}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ))
          : null}
        {unknowns.length ? (
          <>
            <p className="pl-state-title">{targetCopy.section.unknownsTitle}</p>
            <ul className="pl-unknowns">{unknowns.map((unknown) => <li key={unknown.key}>{unknownCopy(unknown.key)}</li>)}</ul>
          </>
        ) : null}
      </section>

      <section aria-labelledby="round-cannot" className="pl-note">
        <h2 id="round-cannot" className="pl-run-title">{t.cannotTitle}</h2>
        <p>{cannotDo(round.key, amazon)}</p>
      </section>

      <div className="pl-run-actions">
        {canPractise ? (
          <>
            <Link className="dh-primary-action" href={roundPracticeHref({ roleName: "", roleProfileId, targetId: target.id, roundKey: round.key })}>
              {t.practise} <ArrowRight size={16} aria-hidden="true" />
            </Link>
            <p className="pl-quiet">{t.practiseNote}</p>
          </>
        ) : (
          <p className="pl-quiet" role="status">{pack?.state === "SHORT_PACK" ? t.shortPack : t.packUnavailable}</p>
        )}
      </div>

      <section aria-labelledby="round-priorities">
        <h2 id="round-priorities" className="pl-run-title">{t.prioritiesTitle}</h2>
        {detail.priorities.length ? (
          <ol className="pl-plain">
            {detail.priorities.slice(0, 3).map((item) => (
              <li key={item.competency_key}>
                <strong>{competencyLabel(item.competency_key) ?? item.competency_key.replace(/_/g, " ")}</strong>
                {item.reason_codes.map(reasonLabel).filter(Boolean).length ? (
                  <span className="pl-source"> · {item.reason_codes.map(reasonLabel).filter(Boolean).join(" · ")}</span>
                ) : null}
              </li>
            ))}
          </ol>
        ) : (
          <p className="pl-quiet">{t.prioritiesEmpty}</p>
        )}
      </section>

      {pack && pack.prompts.length ? (
        <section aria-labelledby="round-questions">
          <h2 id="round-questions" className="pl-run-title">{t.questionsTitle}</h2>
          <p className="pl-source">{t.questionsLabel}</p>
          <ol className="pl-plain">
            {pack.prompts.map((prompt) => (
              <li key={prompt.position}>
                {prompt.text}
                <span className="pl-source"> · {targetCopy.rationale[prompt.rationale_code] ?? targetCopy.rationale.MIRROR_SUGGESTED}</span>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      <section aria-labelledby="round-history">
        <h2 id="round-history" className="pl-run-title">{t.historyTitle}</h2>
        {history.count ? (
          <>
            <p>{t.practisedCount(history.count)}</p>
            <ul className="pl-plain">
              {history.sessions.map((session) => (
                <li key={session.session_id}>
                  {shortDate(session.created_at)} ·{" "}
                  <Link className="dh-text-action" href={`/app/report/${encodeURIComponent(session.session_id)}`}>{t.readReflection}</Link>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="pl-quiet">{t.historyEmpty}</p>
        )}
        <Link className="dh-text-action" href={`/progress/${encodeURIComponent(roleProfileId)}`}>{t.progressLink}</Link>
      </section>
    </div>
  );
}
