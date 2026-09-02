"use client";

import { ArrowLeft, CaretDown, Clock, Info, WarningCircle } from "@phosphor-icons/react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, mirrorApi, type ReportClaim, type ReportEvidence, type ReportResponse } from "@/lib/api";

const groups: Array<{ key: keyof ReportResponse["claims_audit"]; label: string }> = [
  { key: "held", label: "Held" }, { key: "partially_held", label: "Partially held" },
  { key: "walked_back", label: "Walked back" }, { key: "contradicted", label: "Contradicted / unsupported" },
  { key: "insufficient_evidence", label: "Not enough evidence" }, { key: "unverified", label: "Unverified" },
];

const momentLabels: Record<ReportResponse["session_moments"][number]["type"], string> = {
  STRONG_EVIDENCE: "Strong evidence", RECOVERY: "Recovered after hesitation",
  OWNERSHIP_CLARIFICATION: "Ownership became clearer", UNSUPPORTED_SCALE: "Metric could not be substantiated",
  TECHNICAL_DEPTH: "Technical depth",
};

function formatTime(seconds: number) { return `${Math.floor(seconds / 60).toString().padStart(2, "0")}:${Math.floor(seconds % 60).toString().padStart(2, "0")}`; }
function statusLabel(status: ReportClaim["status"]) {
  return status === "CORROBORATED" ? "Held" : status === "PARTIALLY_HELD" ? "Partially held" : status === "INSUFFICIENT_EVIDENCE" ? "Not enough evidence" : status.replaceAll("_", " ").toLowerCase().replace(/^./, (value) => value.toUpperCase());
}
function ClaimEvidence({ evidence }: { evidence: ReportEvidence[] }) {
  if (!evidence.length) return <p className="report-muted">No linked evidence was captured.</p>;
  return <div className="report-evidence-list">{evidence.map((item, index) => <blockquote key={`${item.turn_id ?? "source"}-${index}`}><span className="report-quote-mark">“</span>{item.quote}<footer>{item.turn_id ? `Interview turn${item.timecode_ms != null ? ` · ${formatTime(Math.round(item.timecode_ms / 1000))}` : ""}` : "Source document"} · {item.direction.toLowerCase().replace("_", " ")}</footer></blockquote>)}</div>;
}
function Readiness({ title, value }: { title: string; value: ReportResponse["role_readiness"] }) {
  const numeric = value.low != null && value.high != null;
  return <div className="report-readiness"><p className="report-eyebrow">{title}</p><p className={`report-range ${numeric ? "" : "report-range-muted"}`}>{numeric ? <><span>{value.low}</span><small>–</small><span>{value.high}</span></> : "Not enough signal"}</p><p className="report-readiness-label">{value.label}</p><p className="report-muted">{value.confidence_note}</p></div>;
}

export default function ReportPage() {
  const params = useParams<{ session_id: string }>(); const router = useRouter();
  const [report, setReport] = useState<ReportResponse | null>(null); const [state, setState] = useState<"loading" | "error">("loading"); const [message, setMessage] = useState("");
  useEffect(() => { let active = true; mirrorApi.report(params.session_id).then((value) => active && setReport(value)).catch((reason: unknown) => { if (!active) return; setState("error"); if (reason instanceof ApiError && reason.status === 401) { router.replace("/login?reason=session_expired"); return; } setMessage(reason instanceof ApiError && reason.status === 409 ? "Your interview is still being assessed. Check back when the report is ready." : reason instanceof ApiError && reason.status === 404 ? "We could not find that report." : "Mirror could not load this report. Check your connection and try again."); }); return () => { active = false; }; }, [params.session_id, router]);
  if (state === "loading" && !report) return <main className="report-page"><div className="report-shell" role="status" aria-label="Loading report"><div className="report-skeleton report-skeleton-wide" /><div className="report-skeleton" /><div className="report-skeleton report-skeleton-tall" /></div></main>;
  if (state === "error") return <main className="report-page"><div className="report-shell report-error"><WarningCircle size={28} aria-hidden="true" /><h1>Report unavailable</h1><p>{message}</p><Link className="report-link" href="/app">Return to Mirror</Link></div></main>;
  if (!report) return null;
  const audit = report.claims_audit;
  return <main className="report-page"><div className="report-shell">
    <nav className="report-nav" aria-label="Report navigation"><Link href="/app" className="report-back"><ArrowLeft size={16} aria-hidden="true" /> Mirror</Link><span className="report-nav-meta">{report.session.target_role}</span></nav>
    <header className="report-verdict"><p className="report-eyebrow">Your verdict</p><h1>{report.verdict.label}</h1><p className="report-lede">{report.verdict.summary}</p></header>
    <section className="report-section report-readiness-section" aria-labelledby="readiness-heading"><div className="report-section-heading"><p className="report-eyebrow">Readiness</p><h2 id="readiness-heading">Two signals, kept separate.</h2></div><div className="report-readiness-grid"><Readiness title="Role readiness" value={report.role_readiness} /><Readiness title="Interview readiness" value={report.interview_readiness} /></div></section>
    <section className="report-section report-claims-section" aria-labelledby="claims-heading"><div className="report-section-heading"><p className="report-eyebrow">Evidence record</p><h2 id="claims-heading">What held under questioning</h2><p>Claims are shown as evidence records, not verdicts about you. Start with what the interview supported.</p></div><div className="report-claims-list">{groups.map((group) => { const claims = audit[group.key]; if (!claims.length) return null; return <div key={group.key} className="report-claim-group"><h3>{group.label}<span>{claims.length}</span></h3>{claims.map((claim) => <details className="report-claim" key={claim.id}><summary><span className="report-claim-status">{statusLabel(claim.status)}</span><span className="report-claim-title">{claim.claim_text}</span><CaretDown size={18} aria-hidden="true" /></summary><div className="report-claim-detail"><dl><div><dt>Source</dt><dd>{claim.source.toLowerCase()}</dd></div><div><dt>Explanation</dt><dd>{claim.explanation}</dd></div></dl><ClaimEvidence evidence={claim.evidence} /></div></details>)}</div>; })}</div>{!Object.values(audit).some((items) => items.length) && <p className="report-empty">No claims were available for this interview.</p>}</section>
    <section className="report-section" aria-labelledby="skills-heading"><div className="report-section-heading"><p className="report-eyebrow">Capability evidence</p><h2 id="skills-heading">Skill evidence</h2></div><div className="report-skill-list">{report.skill_assessments.map((skill) => <article className="report-skill" key={skill.skill}><div><h3>{skill.skill}</h3><p className="report-muted">{skill.status === "NOT_ENOUGH_SIGNAL" ? "Not enough signal" : skill.signal_strength}</p></div>{skill.readiness && <p className="report-skill-range">{skill.readiness.low}–{skill.readiness.high}</p>}<p className="report-skill-explanation">{skill.explanation}</p><ClaimEvidence evidence={skill.evidence} /></article>)}{!report.skill_assessments.length && <p className="report-empty">Skill-level evidence will appear here when available.</p>}</div></section>
    <section className="report-section" aria-labelledby="moments-heading"><div className="report-section-heading"><p className="report-eyebrow">Replay markers</p><h2 id="moments-heading">Session moments</h2></div><div className="report-moments">{report.session_moments.map((moment, index) => <article key={`${moment.type}-${moment.turn_id ?? index}`} className="report-moment"><div className="report-moment-time">{moment.timecode_ms != null ? formatTime(Math.round(moment.timecode_ms / 1000)) : "···"}</div><div><h3>{momentLabels[moment.type]}</h3><p>{moment.explanation}</p>{moment.quote && <blockquote>“{moment.quote}”</blockquote>}</div></article>)}{!report.session_moments.length && <p className="report-empty">No time-linked moments were recorded.</p>}</div></section>
    <section className="report-section report-root-cause" aria-labelledby="root-heading"><p className="report-eyebrow">Your main bottleneck</p><h2 id="root-heading">{report.root_cause.replaceAll("_", " ").toLowerCase().replace(/^./, (value) => value.toUpperCase())}</h2><p>Mirror selected one primary area from the evidence in this interview so your next practice session has a clear direction.</p></section>
    <section className="report-trust" aria-labelledby="trust-heading"><Info size={22} aria-hidden="true" /><div><h2 id="trust-heading">What this result means, and what it doesn’t</h2><ul><li>Mirror evaluates evidence captured in this interview.</li><li>AI assessments can make mistakes, and you may challenge an interpretation.</li><li>Skills with too little evidence are not scored.</li><li>Outcome validation status: <strong>{report.trust_and_limitations.outcome_validation_status.replaceAll("_", " ").toLowerCase()}</strong>.</li></ul></div></section>
    <footer className="report-footer"><Clock size={16} aria-hidden="true" /> Completed {new Date(report.session.completed_at).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })} · {formatTime(report.session.duration_seconds)}</footer>
  </div></main>;
}

