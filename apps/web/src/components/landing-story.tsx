"use client";

import "@/styles/landing.css";
import { ArrowDown, ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";
import { Reveal } from "@/components/motion/reveal";
import { MirrorLens } from "@/components/mirror-lens";

const signals = [
  {
    title: "Skills need evidence",
    body: "Skills-based hiring shifts attention from titles alone toward demonstrated capability.",
    source: "LinkedIn Economic Graph, 2025",
    href: "https://economicgraph.linkedin.com/content/dam/me/economicgraph/en-us/PDF/skills-based-hiring-march-2025.pdf",
  },
  {
    title: "Structure matters",
    body: "Job-relevant, structured interviews have stronger evidence than unstructured conversation.",
    source: "McDaniel et al., 1994",
    href: "https://home.ubalt.edu/tmitch/645/articles/McDanieletal1994CriterionValidityInterviewsMeta.pdf",
  },
  {
    title: "Polish is not proof",
    body: "A polished application cannot by itself show ownership, scope, or the basis for an outcome.",
    source: "Mirror product framing",
    href: null,
  },
];

const method = [
  { n: "01", title: "Resume", body: "Claims become starting points." },
  { n: "02", title: "Target role", body: "Requirements set the context." },
  { n: "03", title: "Adaptive interview", body: "Follow-ups seek useful detail." },
  { n: "04", title: "Evidence audit", body: "Support and uncertainty stay visible." },
  { n: "05", title: "Readiness diagnostic", body: "Findings become next actions." },
];

const followUps = [
  { question: "What did you personally own?", status: "Supported" },
  { question: "How was the 18% calculated?", status: "Partial" },
  { question: "What was the baseline?", status: "Not enough signal" },
  { question: "Who else contributed?", status: "Clarify" },
];

const dimensions = [
  ["Ownership", "what you personally owned"],
  ["Scope", "the size and boundaries of the work"],
  ["Impact", "outcomes and supporting measures"],
  ["Consistency", "whether the account holds across answers"],
  ["Role relevance", "connection to the target role"],
  ["Communication", "clarity under probing"],
  ["Evidence strength", "what the session can support"],
];

const comparison = [
  ["Questions", "Role-relevant and adaptive", "Generic or fixed"],
  ["Resume use", "Claims become traceable starting points", "Often treated as background"],
  ["Follow-ups", "Clarify ownership, scope, and measurement", "May stop at the first answer"],
  ["Output", "Evidence-backed diagnostic", "General feedback or a score"],
  ["Uncertainty", "Shown when signal is insufficient", "Often compressed away"],
];

const trustPoints = [
  "No live performance score during the interview.",
  "Findings point to evidence from the session.",
  "Not enough signal is a valid outcome.",
  "Candidate-facing reports do not show hidden reasoning.",
  "Mirror is a diagnostic, not a hiring authority.",
];

export function LandingStory() {
  return (
    <main id="main-content" className="ld-page">
      {/* ---------------------------------------------------------------- */}
      {/* Hero: the product mechanism (claim -> follow-up -> evidence ->   */}
      {/* diagnostic) is the primary visual proof, not decorative art.    */}
      {/* ---------------------------------------------------------------- */}
      <section className="ld-hero shell">
        <div className="ld-hero-copy">
          <p className="ld-eyebrow mono">Evidence-backed interview diagnostic</p>
          <h1 className="ld-hero-title display">Know what your resume can defend.</h1>
          <p className="ld-hero-lede">
            Mirror maps your resume against a target role, then uses an adaptive interview to produce an
            evidence-backed readiness diagnostic.
          </p>
          <div className="ld-hero-actions">
            <Link href="/signup" className="button-primary">
              Start your diagnostic <ArrowRight size={18} />
            </Link>
            <a href="#how-it-works" className="button-secondary">
              See how it works <ArrowDown size={18} />
            </a>
          </div>
          <p className="ld-hero-proofline mono">Resume + target role + adaptive interview + evidence audit</p>
        </div>

        <div className="ld-hero-proof-wrap">
          <div className="ld-hero-proof" aria-label="Illustrative evidence diagnostic example">
            <MirrorLens className="ld-lens--corner" />
            <div className="ld-proof-topline">
              <span>Illustrative diagnostic</span>
              <span>Evidence trace</span>
            </div>

            <div className="ld-proof-row">
              <p className="ld-proof-label">Claim</p>
              <p className="ld-proof-claim">&ldquo;Improved checkout conversion by 18%.&rdquo;</p>
            </div>

            <div className="ld-proof-row">
              <p className="ld-proof-label">Follow-up</p>
              <p className="ld-proof-followup">What part of the experiment did you personally own?</p>
            </div>

            <div className="ld-proof-row">
              <p className="ld-proof-label">Evidence</p>
              <dl className="ld-evidence-grid">
                <div><dt>Ownership</dt><dd>Direct</dd></div>
                <div><dt>Metric support</dt><dd>Partial</dd></div>
                <div><dt>Scope</dt><dd>Verified</dd></div>
                <div><dt>Outcome evidence</dt><dd>Supported</dd></div>
              </dl>
            </div>

            <div className="ld-proof-diagnostic">
              <p className="ld-proof-label">Diagnostic</p>
              <div>
                <div><span>Role readiness</span><strong>72&ndash;80%</strong></div>
                <div><span>Interview readiness</span><strong>64&ndash;73%</strong></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* The problem                                                      */}
      {/* ---------------------------------------------------------------- */}
      <section id="why" className="ld-section">
        <Reveal className="shell ld-section-grid">
          <div className="ld-section-head">
            <p className="ld-eyebrow mono">The problem</p>
            <h2 className="ld-h2 display">The resume is still the entry point. But it is no longer enough.</h2>
          </div>
          <Reveal as="div" stagger className="ld-signal-grid">
            {signals.map((signal) => (
              <article key={signal.title} className="ld-signal hover-lift">
                <h3>{signal.title}</h3>
                <p>{signal.body}</p>
                {signal.href ? (
                  <a href={signal.href} target="_blank" rel="noreferrer">
                    {signal.source}
                  </a>
                ) : (
                  <span>{signal.source}</span>
                )}
              </article>
            ))}
          </Reveal>
        </Reveal>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* How it works                                                     */}
      {/* ---------------------------------------------------------------- */}
      <section id="how-it-works" className="ld-section">
        <Reveal className="shell">
          <p className="ld-eyebrow mono">How Mirror works</p>
          <h2 className="ld-h2 display">A connected trail from claim to diagnostic.</h2>
          <Reveal as="ol" stagger className="ld-method">
            {method.map((step) => (
              <li key={step.n}>
                <b className="mono">{step.n}</b>
                <strong>{step.title}</strong>
                <span>{step.body}</span>
              </li>
            ))}
          </Reveal>
        </Reveal>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* A claim under questioning                                        */}
      {/* ---------------------------------------------------------------- */}
      <Reveal as="section" className="ld-section">
        <div className="shell ld-two-col">
          <div className="ld-section-head">
            <p className="ld-eyebrow mono">A claim under questioning</p>
            <h2 className="ld-h2 display">Precision arrives one question at a time.</h2>
            <p className="ld-copy">
              Mirror does not decide whether a person is truthful. It asks for enough context to understand what an
              answer can&mdash;and cannot&mdash;support.
            </p>
          </div>
          <div className="ld-ledger">
            <p className="ld-ledger-claim">&ldquo;Improved checkout conversion by 18%.&rdquo;</p>
            {followUps.map((item, index) => (
              <div key={item.question} className="ld-ledger-row">
                <span className="mono">0{index + 1}</span>
                <p>{item.question}</p>
                <em>{item.status}</em>
              </div>
            ))}
          </div>
        </div>
      </Reveal>

      {/* ---------------------------------------------------------------- */}
      {/* What Mirror evaluates                                            */}
      {/* ---------------------------------------------------------------- */}
      <Reveal as="section" className="ld-section">
        <div className="shell ld-two-col">
          <div className="ld-section-head">
            <p className="ld-eyebrow mono">What Mirror evaluates</p>
            <h2 className="ld-h2 display">Not confidence. The evidence behind it.</h2>
          </div>
          <Reveal as="dl" stagger className="ld-dimensions">
            {dimensions.map(([name, detail], index) => (
              <div key={name}>
                <dt className="mono">{String(index + 1).padStart(2, "0")}</dt>
                <dd>
                  <strong>{name}</strong>
                  <span>{detail}</span>
                </dd>
              </div>
            ))}
          </Reveal>
        </div>
      </Reveal>

      {/* ---------------------------------------------------------------- */}
      {/* Illustrative diagnostic                                          */}
      {/* ---------------------------------------------------------------- */}
      <Reveal as="section" className="ld-section">
        <div className="shell">
          <p className="ld-eyebrow mono">Illustrative diagnostic</p>
          <div className="ld-diagnostic">
            <div>
              <span>Role readiness</span>
              <strong>72&ndash;80%</strong>
              <small>Evidence supports several target-role claims.</small>
            </div>
            <div>
              <span>Interview readiness</span>
              <strong>64&ndash;73%</strong>
              <small>Ownership and baseline need more precision.</small>
            </div>
            <div>
              <span>Claims audit</span>
              <b>1 supported &middot; 1 partial &middot; 1 needs signal</b>
            </div>
            <div>
              <span>Recommended action</span>
              <b>Practice explaining baseline, ownership, and scope.</b>
            </div>
          </div>
        </div>
      </Reveal>

      {/* ---------------------------------------------------------------- */}
      {/* Comparison                                                       */}
      {/* ---------------------------------------------------------------- */}
      <Reveal as="section" className="ld-section">
        <div className="shell">
          <p className="ld-eyebrow mono">Not another generic mock interview</p>
          <h2 className="ld-h2 display">A diagnostic has a different job.</h2>
          <div className="ld-comparison" role="table" aria-label="Mirror compared with a generic mock interview">
            <div role="row" className="ld-comparison-head">
              <span>Approach</span>
              <span>Mirror</span>
              <span>Generic mock interview</span>
            </div>
            {comparison.map(([label, mirror, generic]) => (
              <div role="row" key={label} className="ld-comparison-row">
                <strong>{label}</strong>
                <span>{mirror}</span>
                <span>{generic}</span>
              </div>
            ))}
          </div>
        </div>
      </Reveal>

      {/* ---------------------------------------------------------------- */}
      {/* Trust and limits                                                 */}
      {/* ---------------------------------------------------------------- */}
      <Reveal as="section" className="ld-section">
        <div className="shell ld-two-col">
          <div className="ld-section-head">
            <p className="ld-eyebrow mono">Trust and limits</p>
            <h2 className="ld-h2 display">Useful signal should remain accountable.</h2>
          </div>
          <Reveal as="ul" stagger className="ld-trust-list">
            {trustPoints.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </Reveal>
        </div>
      </Reveal>

      {/* ---------------------------------------------------------------- */}
      {/* Final CTA                                                        */}
      {/* ---------------------------------------------------------------- */}
      <Reveal as="section" className="ld-section ld-final">
        <div className="shell ld-final-inner">
          <div>
            <p className="ld-eyebrow mono">Start with the evidence</p>
            <h2 className="ld-h2 display">Know what holds before the interview asks.</h2>
          </div>
          <div className="ld-hero-actions">
            <Link href="/signup" className="button-primary">
              Start your diagnostic <ArrowRight size={18} />
            </Link>
            <a href="#how-it-works" className="button-secondary">
              See how it works <ArrowDown size={18} />
            </a>
          </div>
        </div>
      </Reveal>

      <footer className="ld-footer">
        <div className="shell ld-footer-inner">
          <p>Mirror evaluates evidence from this session. AI can make mistakes. Outcome validation is still in progress.</p>
          <p>by Pathwisse</p>
        </div>
      </footer>
    </main>
  );
}
