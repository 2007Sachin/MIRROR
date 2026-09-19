"use client";

import {
  ArrowLeft,
  CaretDown,
  Clock,
  Info,
  WarningCircle,
} from "@phosphor-icons/react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ApiError,
  mirrorApi,
  type ReportClaim,
  type ReportEvidence,
  type ReportResponse,
} from "@/lib/api";
import { Reveal } from "@/components/motion/reveal";
import "@/styles/sessions.css";

const groups: Array<{
  key: keyof ReportResponse["claims_audit"];
  label: string;
}> = [
  { key: "held", label: "Held" },
  { key: "partially_held", label: "Partially held" },
  { key: "walked_back", label: "Walked back" },
  { key: "contradicted", label: "Contradicted / unsupported" },
  { key: "insufficient_evidence", label: "Not enough evidence" },
  { key: "unverified", label: "Unverified" },
];

const momentLabels: Record<
  ReportResponse["session_moments"][number]["type"],
  string
> = {
  STRONG_EVIDENCE: "Strong evidence",
  RECOVERY: "Recovered after hesitation",
  OWNERSHIP_CLARIFICATION: "Ownership became clearer",
  UNSUPPORTED_SCALE: "Metric could not be substantiated",
  TECHNICAL_DEPTH: "Technical depth",
};

function formatTime(seconds: number) {
  return `${Math.floor(seconds / 60).toString().padStart(2, "0")}:${Math.floor(seconds % 60).toString().padStart(2, "0")}`;
}

function statusLabel(status: ReportClaim["status"]) {
  if (status === "CORROBORATED") return "Held";
  if (status === "PARTIALLY_HELD") return "Partially held";
  if (status === "INSUFFICIENT_EVIDENCE") return "Not enough evidence";
  return status
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (value) => value.toUpperCase());
}

/** The report's one status-color vocabulary: pulse = supported, brass =
 * partial/uncertain, danger = unsupported/contradicted, and a deliberately
 * neutral silver for "not enough evidence" -- absence of evidence is not
 * the same claim state as a contradiction and must not read as a failure. */
function statusClass(status: ReportClaim["status"]) {
  if (status === "CORROBORATED") return "is-supported";
  if (status === "PARTIALLY_HELD") return "is-partial";
  if (status === "WALKED_BACK" || status === "CONTRADICTED") return "is-unsupported";
  return "is-neutral";
}

function ClaimEvidence({ evidence }: { evidence: ReportEvidence[] }) {
  if (!evidence.length) {
    return <p className="dg-muted">No linked evidence was captured.</p>;
  }
  return (
    <div className="dg-evidence-list">
      {evidence.map((item, index) => (
        <blockquote key={`${item.turn_id ?? "source"}-${index}`}>
          <span className="dg-quote-mark">“</span>
          {item.quote}
          <footer>
            {item.turn_id
              ? `Interview turn${
                  item.timecode_ms != null
                    ? ` · ${formatTime(Math.round(item.timecode_ms / 1000))}`
                    : ""
                }`
              : "Source document"}
            {" · "}
            {item.direction.toLowerCase().replace("_", " ")}
          </footer>
        </blockquote>
      ))}
    </div>
  );
}

/** A range, never a single number, paired immediately with its qualitative
 * label and signal strength -- the deliberate alternative to a gauge or a
 * bare score (mirror-visual-design: show uncertainty explicitly). */
function Readiness({
  title,
  value,
}: {
  title: string;
  value: ReportResponse["role_readiness"];
}) {
  const numeric = value.low != null && value.high != null;
  return (
    <div className="dg-readiness">
      <p className="dg-eyebrow">{title}</p>
      <div className="dg-readiness-row">
        <p className={`dg-range ${numeric ? "" : "dg-range-muted"}`}>
          {numeric ? (
            <>
              <span>{value.low}</span>
              <small>–</small>
              <span>{value.high}</span>
            </>
          ) : (
            "Not enough signal"
          )}
        </p>
        <span className="dg-readiness-label">{value.label}</span>
      </div>
      {value.signal_strength ? <p className="dg-signal">{value.signal_strength}</p> : null}
      <p className="dg-muted">{value.confidence_note}</p>
    </div>
  );
}

export default function ReportPage() {
  const params = useParams<{ session_id: string }>();
  const router = useRouter();
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [state, setState] = useState<"loading" | "processing" | "error">(
    "loading",
  );
  const [message, setMessage] = useState("");
  const [retryable, setRetryable] = useState(false);
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;

    const fail = (reason: unknown) => {
      if (!active) return;
      if (reason instanceof ApiError && reason.status === 401) {
        router.replace("/login?reason=session_expired");
        return;
      }
      setRetryable(false);
      setState("error");
      setMessage(
        reason instanceof ApiError && reason.status === 404
          ? "We could not find that report."
          : "Mirror could not load this report. Check your connection and try again.",
      );
    };

    const loadReport = async () => {
      try {
        const value = await mirrorApi.report(params.session_id);
        if (active) {
          setReport(value);
          setState("loading");
        }
      } catch (reason) {
        if (!(reason instanceof ApiError) || reason.status !== 409) {
          fail(reason);
          return;
        }
        try {
          const processing = await mirrorApi.assessmentStatus(params.session_id);
          if (!active) return;
          if (processing.status === "FAILED") {
            setRetryable(true);
            setState("error");
            setMessage(
              "Your interview has been saved. Mirror couldn't finish evaluating the evidence, so the assessment can be retried without repeating the interview.",
            );
            return;
          }
          setState("processing");
          attempts += 1;
          if (attempts < 24) timer = setTimeout(loadReport, 5000);
          else {
            setState("error");
            setMessage(
              "Your assessment is taking longer than expected. Please return shortly to check the report.",
            );
          }
        } catch (statusReason) {
          fail(statusReason);
        }
      }
    };

    void loadReport();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [params.session_id, router]);

  async function retryEvaluation() {
    setRetrying(true);
    try {
      await mirrorApi.retryAssessment(params.session_id);
      router.replace("/dashboard");
    } catch (reason) {
      setMessage(
        reason instanceof ApiError
          ? reason.message
          : "Mirror could not retry this evaluation.",
      );
    } finally {
      setRetrying(false);
    }
  }

  if (state === "loading" && !report) {
    return (
      <main id="main-content" className="dg-page">
        <div
          className="dg-shell"
          role="status"
          aria-label="Loading report"
        >
          <div className="dg-skeleton dg-skeleton-wide" />
          <div className="dg-skeleton" />
          <div className="dg-skeleton dg-skeleton-tall" />
        </div>
      </main>
    );
  }

  if (state === "processing") {
    return (
      <main id="main-content" className="dg-page">
        <div className="dg-shell dg-status-shell" role="status">
          <Clock size={28} aria-hidden="true" />
          <h1>Evaluating evidence</h1>
          <p>
            Mirror is examining your answers against your claims, available
            evidence and the expectations of the role.
          </p>
          <Link className="dg-back" href="/dashboard">
            Return to your evidence workspace
          </Link>
        </div>
      </main>
    );
  }

  if (state === "error") {
    return (
      <main id="main-content" className="dg-page">
        <div className="dg-shell dg-status-shell">
          <WarningCircle size={28} aria-hidden="true" />
          <h1>
            {retryable
              ? "We couldn't complete the diagnostic"
              : "Diagnostic unavailable"}
          </h1>
          <p>{message}</p>
          <div className="dg-status-actions">
            {retryable ? (
              <button
                className="dg-back"
                type="button"
                onClick={() => void retryEvaluation()}
                disabled={retrying}
              >
                {retrying ? "Requesting retry…" : "Retry evaluation"}
              </button>
            ) : null}
            <Link className="dg-back" href="/dashboard">
              Return to your evidence workspace
            </Link>
          </div>
        </div>
      </main>
    );
  }

  if (!report) return null;
  const audit = report.claims_audit;

  return (
    <main id="main-content" className="dg-page">
      <div className="dg-shell">
        <nav className="dg-nav" aria-label="Report navigation">
          <Link href="/dashboard" className="dg-back">
            <ArrowLeft size={16} aria-hidden="true" /> Evidence workspace
          </Link>
          <span className="dg-nav-meta">{report.session.target_role}</span>
        </nav>

        <Reveal as="header" className="dg-verdict">
          <p className="dg-eyebrow">Your verdict</p>
          <h1>{report.verdict.label}</h1>
          <p className="dg-lede">{report.verdict.summary}</p>
        </Reveal>

        <section className="dg-section" aria-labelledby="readiness-heading">
          <Reveal>
            <div className="dg-section-heading">
              <p className="dg-eyebrow">Readiness</p>
              <h2 id="readiness-heading">Two signals, kept separate.</h2>
            </div>
            <div className="dg-readiness-grid">
              <Readiness title="Role readiness" value={report.role_readiness} />
              <Readiness
                title="Interview readiness"
                value={report.interview_readiness}
              />
            </div>
            <p className="dg-readiness-caption">
              Shown as a range with a stated signal strength, not a single
              score — readiness is an estimate built from this interview's
              evidence, not a placement prediction.
            </p>
          </Reveal>
        </section>

        <section className="dg-section" aria-labelledby="claims-heading">
          <Reveal className="dg-section-heading">
            <p className="dg-eyebrow">Evidence record</p>
            <h2 id="claims-heading">What held under questioning</h2>
            <p>
              Claims are shown as evidence records, not verdicts about you.
              Start with what the interview supported.
            </p>
          </Reveal>
          <Reveal as="div" stagger>
            {groups.map((group) => {
              const claims = audit[group.key];
              if (!claims.length) return null;
              return (
                <div key={group.key} className="dg-claim-group">
                  <h3 className="dg-claim-group-heading">
                    {group.label}<span>{claims.length}</span>
                  </h3>
                  {claims.map((claim) => (
                    <details className="dg-claim" key={claim.id}>
                      <summary className="dg-claim-row">
                        <span className={`dg-status ${statusClass(claim.status)}`}>
                          {statusLabel(claim.status)}
                        </span>
                        <span className="dg-claim-title">
                          {claim.claim_text}
                        </span>
                        <CaretDown size={18} aria-hidden="true" />
                      </summary>
                      <div className="dg-claim-detail">
                        <dl>
                          <div><dt>Source</dt><dd>{claim.source.toLowerCase()}</dd></div>
                          <div><dt>Explanation</dt><dd>{claim.explanation}</dd></div>
                        </dl>
                        <ClaimEvidence evidence={claim.evidence} />
                      </div>
                    </details>
                  ))}
                </div>
              );
            })}
          </Reveal>
          {!Object.values(audit).some((items) => items.length) ? (
            <p className="dg-empty">
              No claims were available for this interview.
            </p>
          ) : null}
        </section>

        <section className="dg-section" aria-labelledby="skills-heading">
          <Reveal className="dg-section-heading">
            <p className="dg-eyebrow">Capability evidence</p>
            <h2 id="skills-heading">Skill evidence</h2>
          </Reveal>
          <Reveal as="div" stagger className="dg-skill-list">
            {report.skill_assessments.map((skill) => (
              <article className="dg-skill" key={skill.skill}>
                <div className="dg-skill-head">
                  <h3>{skill.skill}</h3>
                  <span
                    className={`dg-status ${
                      skill.status === "NOT_ENOUGH_SIGNAL" ? "is-neutral" : "is-supported"
                    }`}
                  >
                    {skill.status === "NOT_ENOUGH_SIGNAL"
                      ? "Not enough signal"
                      : skill.signal_strength}
                  </span>
                </div>
                {skill.readiness ? (
                  <p className="dg-skill-range">
                    {skill.readiness.low}–{skill.readiness.high}
                  </p>
                ) : null}
                <p className="dg-skill-explanation">{skill.explanation}</p>
                <ClaimEvidence evidence={skill.evidence} />
              </article>
            ))}
          </Reveal>
          {!report.skill_assessments.length ? (
            <p className="dg-empty">
              Skill-level evidence will appear here when available.
            </p>
          ) : null}
        </section>

        <section className="dg-section" aria-labelledby="moments-heading">
          <Reveal className="dg-section-heading">
            <p className="dg-eyebrow">Replay markers</p>
            <h2 id="moments-heading">Session moments</h2>
          </Reveal>
          <Reveal as="div" stagger className="dg-moments">
            {report.session_moments.map((moment, index) => (
              <article
                key={`${moment.type}-${moment.turn_id ?? index}`}
                className="dg-moment"
              >
                <div className="dg-moment-time">
                  {moment.timecode_ms != null
                    ? formatTime(Math.round(moment.timecode_ms / 1000))
                    : "···"}
                </div>
                <div>
                  <h3>{momentLabels[moment.type]}</h3>
                  <p>{moment.explanation}</p>
                  {moment.quote ? <blockquote>“{moment.quote}”</blockquote> : null}
                </div>
              </article>
            ))}
          </Reveal>
          {!report.session_moments.length ? (
            <p className="dg-empty">
              No time-linked moments were recorded.
            </p>
          ) : null}
        </section>

        <section className="dg-section dg-root-cause" aria-labelledby="root-heading">
          <Reveal>
            <p className="dg-eyebrow">Your main bottleneck</p>
            <h2 id="root-heading">
              {report.root_cause
                .replaceAll("_", " ")
                .toLowerCase()
                .replace(/^./, (value) => value.toUpperCase())}
            </h2>
            <p>
              Mirror selected one primary area from the evidence in this
              interview so your next practice session has a clear direction.
            </p>
          </Reveal>
        </section>

        {/* Candidate-safety critical: always rendered, never gated behind
            scroll-triggered opacity so it cannot be missed or read as
            de-emphasized. */}
        <section className="dg-trust" aria-labelledby="trust-heading">
          <Info size={22} aria-hidden="true" />
          <div>
            <h2 id="trust-heading">What this result means, and what it doesn’t</h2>
            <ul>
              <li>Mirror evaluates evidence captured in this interview.</li>
              <li>
                AI assessments can make mistakes, and you may challenge an
                interpretation.
              </li>
              <li>Skills with too little evidence are not scored.</li>
              <li>
                Outcome validation status:{" "}
                <strong>
                  {report.trust_and_limitations.outcome_validation_status
                    .replaceAll("_", " ")
                    .toLowerCase()}
                </strong>
                .
              </li>
            </ul>
          </div>
        </section>

        <footer className="dg-footer">
          <Clock size={16} aria-hidden="true" /> Completed{" "}
          {new Date(report.session.completed_at).toLocaleDateString(undefined, {
            year: "numeric",
            month: "long",
            day: "numeric",
          })}{" "}
          · {formatTime(report.session.duration_seconds)}
        </footer>
      </div>
    </main>
  );
}
