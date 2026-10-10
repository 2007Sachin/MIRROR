"use client";

import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageAlert } from "@/components/workspace/page-shell";
import { CandidateStagePlanEditor } from "@/components/plan/candidate-stage-plan-editor";
import { getBlueprint, targetsForRole, type BlueprintView, type ClaimView, type TargetView } from "@/lib/api-targets";
import {
  candidateStageRoundGroups,
  claimCopy,
  claimMatchesTargetScope,
  conflictCopy,
  countryLabel,
  failureKind,
  researchState,
  roundCovers,
  roundHref,
  roundLabel,
  roundPracticeHref,
  shortDate,
  sourceLabel,
  targetCopy,
  targetLine,
  unknownCopy,
} from "@/lib/copy-targets";
import { ApiError } from "@/lib/api";
import { activeTargetsForRole, createRequestSequence, selectTargetForRole } from "@/lib/target-recovery";

const t = targetCopy.section;

type Overview =
  | { kind: "loading-list" }
  | { kind: "hidden" }
  | { kind: "choose-target"; targets: TargetView[] }
  | { kind: "loading"; target: TargetView }
  | { kind: "unavailable"; target: TargetView }
  | { kind: "error"; target: TargetView }
  | { kind: "ready"; target: TargetView; view: BlueprintView };

/**
 * My plan, section A: how interviews for this role tend to run, for the role's interview target.
 * Fully separate from the plan below: anything missing, switched off or failing here stays inside
 * this section (or hides it) and never changes the plan areas.
 */
export function TargetOverview({
  roleProfileId,
  roleName,
  initialTargetId,
  onPrimary,
}: {
  roleProfileId: string;
  roleName: string;
  initialTargetId?: string;
  /** Told whether this section shows the page's one filled action, so the plan below can step back. */
  onPrimary: (shown: boolean) => void;
}) {
  const [state, setState] = useState<Overview>({ kind: "loading-list" });
  const [selectedTargetId, setSelectedTargetId] = useState<string | null>(null);
  const [roleTargets, setRoleTargets] = useState<TargetView[]>([]);
  const [editorDirty, setEditorDirty] = useState(false);
  const requestSequence = useRef(createRequestSequence());

  const loadTarget = useCallback(async (target: TargetView, isCurrent: () => boolean = () => true) => {
    setState({ kind: "loading", target });
    try {
      const view = await getBlueprint(target.id);
      if (!isCurrent()) return;
      setState(researchState(view) === "UNAVAILABLE" ? { kind: "unavailable", target } : { kind: "ready", target, view });
    } catch (reason) {
      if (!isCurrent()) return;
      const quiet = reason instanceof ApiError && failureKind(reason.status) === "UNAVAILABLE";
      setState({ kind: quiet ? "unavailable" : "error", target });
    }
  }, []);

  const load = useCallback(async (requestedTargetId?: string, isCurrent: () => boolean = () => true) => {
    const requestId = requestSequence.current.next();
    const current = () => requestSequence.current.isCurrent(requestId) && isCurrent();
    try {
      const found = await targetsForRole(roleProfileId);
      if (!current()) return;
      if (found.kind !== "TARGETS") {
        setSelectedTargetId(null);
        setRoleTargets([]);
        return setState({ kind: "hidden" });
      }
      const availableTargets = activeTargetsForRole(found.targets, roleProfileId);
      setRoleTargets(availableTargets);
      const target = selectTargetForRole(availableTargets, roleProfileId, requestedTargetId);
      if (!target || target.status !== "ACTIVE" || target.role_profile_id !== roleProfileId) {
        setSelectedTargetId(null);
        return availableTargets.length
          ? setState({ kind: "choose-target", targets: availableTargets })
          : setState({ kind: "hidden" });
      }
      setSelectedTargetId(target.id);
      await loadTarget(target, current);
    } catch {
      if (!current()) return;
      return setState({ kind: "hidden" }); // the plan works without this section
    }
  }, [loadTarget, roleProfileId]);

  function switchTarget(targetId: string) {
    if (!targetId || targetId === selectedTargetId) return;
    const stageCopy = targetCopy.section.candidateStages;
    if (editorDirty && !window.confirm(stageCopy.switchConfirm)) return;
    setEditorDirty(false);
    void load(targetId);
  }

  useEffect(() => {
    let active = true;
    void load(initialTargetId, () => active);
    return () => { active = false; };
  }, [initialTargetId, load]);

  const primary = state.kind === "ready" && state.view.rounds.length > 0;
  useEffect(() => onPrimary(primary), [onPrimary, primary]);

  if (state.kind === "hidden" || state.kind === "loading-list") return null;
  if (state.kind === "choose-target") {
    const stageCopy = targetCopy.section.candidateStages;
    return (
      <section className="pl-run" aria-labelledby="pl-run-title">
        <h2 id="pl-run-title" className="pl-run-title">{t.title}</h2>
        <label className="pl-target-picker">
          <span>{stageCopy.selectTarget}</span>
          <span className="pl-quiet">{stageCopy.selectTargetHelp}</span>
          <select className="field" value="" onChange={(event) => switchTarget(event.target.value)}>
            <option value="">{stageCopy.selectTarget}</option>
            {state.targets.map((item) => <option key={item.id} value={item.id}>{targetLine(item)}</option>)}
          </select>
        </label>
      </section>
    );
  }
  const target = state.target;

  return (
    <section className="pl-run" aria-labelledby="pl-run-title" aria-busy={state.kind === "loading" || undefined}>
      <h2 id="pl-run-title" className="pl-run-title">{t.title}</h2>
      {roleTargets.length > 1 ? (
        <label className="pl-target-picker">
          <span>{targetCopy.section.candidateStages.selectTarget}</span>
          <select className="field" value={target.id} onChange={(event) => switchTarget(event.target.value)}>
            {roleTargets.map((item) => <option key={item.id} value={item.id}>{targetLine(item)}</option>)}
          </select>
        </label>
      ) : null}
      <p className="pl-target-line">{targetLine(target)}</p>
      {state.kind === "loading" ? (
        <div className="pl-skeleton">
          <p role="status" aria-live="polite" className="sr-only">{t.loading}</p>
          <span aria-hidden="true" />
          <span aria-hidden="true" />
          <span aria-hidden="true" />
        </div>
      ) : null}
      {state.kind === "unavailable" ? (
        <p className="pl-quiet">
          {t.unavailable}{" "}
          <button type="button" className="dh-text-action" onClick={() => void load(selectedTargetId ?? undefined)}>{t.retry}</button>
        </p>
      ) : null}
      {state.kind === "error" ? <PageAlert message={t.error} onRetry={() => void load(selectedTargetId ?? undefined)} retryLabel={t.retry} /> : null}
      {state.kind === "ready" ? <Ready target={target} view={state.view} roleProfileId={roleProfileId} roleName={roleName} onSaved={(view) => setState({ kind: "ready", target, view })} onDirtyChange={setEditorDirty} /> : null}
    </section>
  );
}

function Ready({ target, view, roleProfileId, roleName, onSaved, onDirtyChange }: {
  target: TargetView;
  view: BlueprintView;
  roleProfileId: string;
  roleName: string;
  onSaved: (view: BlueprintView) => void;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const research = researchState(view);
  const claims = view.claims.filter((claim) => claimMatchesTargetScope(claim, target) && claimCopy(claim.key, claim.version));
  const conflicts = view.conflicts.filter((conflict) => conflictCopy(conflict.key) && conflict.claims.some((claim) => claimMatchesTargetScope(claim, target) && claimCopy(claim.key, claim.version)));
  const unknowns = view.unknowns.filter((unknown) => unknownCopy(unknown.key));
  const researched = research === "RESEARCHED" || research === "GENERAL_ONLY";
  const rounds = [...view.rounds].sort((a, b) => a.ordinal - b.ordinal).filter((round) => roundLabel(round.label_key));
  const stagePlan = view.candidate_stage_plan;
  const stageCopy = targetCopy.section.candidateStages;
  const mappedStages = stagePlan?.candidate_stage_state === "KNOWN"
    ? candidateStageRoundGroups(target.role_family_key, stagePlan.candidate_stages, rounds.map((round) => round.key))
    : [];
  const first = rounds[0];
  const anyLinked = rounds.some((round) => round.basis === "PUBLISHED_GUIDANCE");

  return (
    <>
      <section className="pl-stage-plan" aria-labelledby="pl-stage-plan-title">
        <h3 id="pl-stage-plan-title" className="pl-run-sub">{stageCopy.overviewTitle}</h3>
        <p className="pl-quiet">{stageCopy.mappingIntro}</p>
        <p className="pl-quiet">{stageCopy.editorIntro}</p>
        <CandidateStagePlanEditor target={target} view={view} compact onSaved={onSaved} onDirtyChange={onDirtyChange} />
        {mappedStages.length ? (
          <>
            <h4 className="pl-state-title">{stageCopy.mappingTitle}</h4>
            <ul className="pl-stages">
              {mappedStages.map((group) => {
                const round = rounds.find((item) => item.key === group.roundKey);
                if (!round) return null;
                const stageLabels = group.stages.map((stage) => {
                  const label = stage.kind === "OTHER" ? stage.custom_label?.trim() : stageCopy.stageKinds[stage.kind];
                  return `${label || stageCopy.stageKinds[stage.kind] || "Stage"}${stage.certainty === "UNCERTAIN" ? ` · ${stageCopy.uncertain}` : ""}`;
                });
                return (
                  <li key={group.roundKey}>
                    <p className="pl-state-title">{roundLabel(round.label_key)}</p>
                    <p className="pl-source">{stageLabels.join(" · ")}</p>
                    <Link className="dh-text-action" href={roundPracticeHref({ roleName, roleProfileId, targetId: target.id, roundKey: round.key })}>
                      {stageCopy.practice(stageLabels.join(", "))} <ArrowRight size={15} aria-hidden="true" />
                    </Link>
                  </li>
                );
              })}
            </ul>
          </>
        ) : <p className="pl-quiet">{stagePlan?.candidate_stage_state === "KNOWN" ? stageCopy.noMapping : stageCopy.noStages}</p>}
      </section>
      {research === "NOT_YET_RESEARCHED" ? (
        <div className="pl-state">
          <p className="pl-state-title">{t.notYetResearchedTitle}</p>
          <p>{t.notYetResearched(target.company_label, countryLabel(target))}</p>
        </div>
      ) : null}
      {research === "NO_NOTES_FOR_COMPANY" ? <p className="pl-quiet">{t.noNotes(target.company_label)}</p> : null}
      {research === "GENERAL_ONLY" ? <p className="pl-scope">{t.generalOnly}</p> : null}
      {research === "RESEARCHED" ? <p className="pl-scope">{t.researchedScope}</p> : null}

      {researched && claims.length ? (
        <>
          <h3 className="pl-run-sub">{t.publishedGuidanceTitle}</h3>
          <ul className="pl-stages">
            {claims.map((claim) => (
              <li key={claim.key}>
                <p>{claimCopy(claim.key, claim.version)}</p>
                <p className="pl-source">{sourceLabel(claim, target.company_label)}</p>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {researched && !claims.length && !conflicts.length ? <p className="pl-quiet">{t.nothingYet}</p> : null}

      {researched && conflicts.length
        ? conflicts.map((conflict) => (
            <section key={conflict.key} className="pl-conflict" aria-labelledby={`conflict-${conflict.key}`}>
              <h3 id={`conflict-${conflict.key}`} className="pl-run-sub">{t.conflictTitle}</h3>
              <p>{conflictCopy(conflict.key)}</p>
              <ul className="pl-conflict-sides">
                {conflict.claims.filter((claim) => claimCopy(claim.key, claim.version)).map((claim) => (
                  <li key={claim.key}>
                    <p>{claimCopy(claim.key, claim.version)}</p>
                    <p className="pl-source">{sourceLabel(claim, target.company_label)}</p>
                  </li>
                ))}
              </ul>
              <p className="pl-quiet">{t.conflictNote}</p>
            </section>
          ))
        : null}

      {unknowns.length ? (
        <>
          <h3 className="pl-run-sub">{t.unknownsTitle}</h3>
          <ul className="pl-unknowns">
            {unknowns.map((unknown) => <li key={unknown.key}>{unknownCopy(unknown.key)}</li>)}
          </ul>
        </>
      ) : null}

      {researched && claims.length ? <Sources claims={[...claims, ...conflicts.flatMap((c) => c.claims)]} /> : null}

      {rounds.length ? (
        <>
          <h3 className="pl-run-sub">{t.mirrorCoverageTitle}</h3>
          <p className="pl-quiet">{anyLinked ? t.roundsIntroLinked : t.roundsIntroSuggested}</p>
          <ol className="pl-rounds">
            {rounds.map((round) => (
              <li key={round.key} id={`round-${round.key}`}>
                <Link href={roundHref(roleProfileId, round.key, target.id)} aria-describedby={`round-${round.key}-covers round-${round.key}-basis`}>
                  {roundLabel(round.label_key)} <ArrowRight size={15} aria-hidden="true" />
                </Link>
                <p id={`round-${round.key}-covers`}>{roundCovers(round.label_key)}</p>
                <p id={`round-${round.key}-basis`} className="pl-source">{targetCopy.basis[round.basis] ?? targetCopy.basis.MIRROR_SUGGESTED}</p>
                {round.presence === "CONDITIONAL" ? <p className="pl-quiet">{targetCopy.round.conditional}</p> : null}
              </li>
            ))}
          </ol>
          {first ? (
            <div className="pl-run-actions">
              <Link
                className="dh-primary-action"
                href={roundPracticeHref({ roleName, roleProfileId, targetId: target.id, roundKey: first.key })}
              >
                {t.practiseFirst(roundLabel(first.label_key) ?? "")} <ArrowRight size={16} aria-hidden="true" />
              </Link>
            </div>
          ) : null}
        </>
      ) : null}
    </>
  );
}

function Sources({ claims }: { claims: ClaimView[] }) {
  const seen = new Map<string, ClaimView["sources"][number]>();
  for (const claim of claims) for (const source of claim.sources) if (!seen.has(source.url)) seen.set(source.url, source);
  if (!seen.size) return null;
  return (
    <details className="pl-sources">
      <summary>{t.sourcesToggle}</summary>
      <ul>
        {[...seen.values()].map((source) => (
          <li key={source.url}>
            <a href={source.url} rel="noreferrer">{source.publisher}</a>
            {" · "}
            {targetCopy.source.checked(shortDate(source.retrieved_at))}
            {source.published_at ? null : ` · ${targetCopy.source.noPublishDate}`}
          </li>
        ))}
      </ul>
    </details>
  );
}
