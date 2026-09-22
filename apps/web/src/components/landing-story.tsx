"use client";

import "@/styles/landing.css";
import { ArrowDown, ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";
import { Reveal } from "@/components/motion/reveal";
import { MirrorLens } from "@/components/mirror-lens";
import { landing as t, meta } from "@/lib/copy";

export function LandingStory() {
  return (
    <main id="main-content" className="ld-page">
      <section className="ld-hero shell">
        <div className="ld-hero-copy">
          <p className="ld-eyebrow mono">{t.hero.eyebrow}</p>
          <h1 className="ld-hero-title display">{t.hero.title}</h1>
          <p className="ld-hero-lede">{t.hero.subline}</p>
          <div className="ld-hero-actions">
            <Link href="/signup" className="button-primary">
              {t.hero.primaryCta} <ArrowRight size={18} />
            </Link>
            <a href="#sample-reflection" className="button-secondary">
              {t.hero.secondaryCta} <ArrowDown size={18} />
            </a>
          </div>
          <p className="ld-hero-proofline mono">{t.hero.underButtons}</p>
        </div>

        <div className="ld-hero-proof-wrap">
          <div className="ld-hero-proof" aria-label={t.heroCard.ariaLabel}>
            <MirrorLens className="ld-lens--corner" />
            <div className="ld-proof-topline">
              <span>{t.heroCard.label}</span>
            </div>

            <div className="ld-proof-row">
              <p className="ld-proof-label">{t.heroCard.storyLabel}</p>
              <p className="ld-proof-claim">{t.heroCard.story}</p>
            </div>

            <div className="ld-proof-row">
              <p className="ld-proof-label">{t.heroCard.followUpLabel}</p>
              <p className="ld-proof-followup">{t.heroCard.followUp}</p>
            </div>

            <div className="ld-proof-row">
              <p className="ld-proof-label">{t.heroCard.cameThroughLabel}</p>
              <dl className="ld-evidence-grid">
                {t.heroCard.cameThrough.map(([name, value]) => (
                  <div key={name}><dt>{name}</dt><dd>{value}</dd></div>
                ))}
              </dl>
            </div>

            <div className="ld-proof-diagnostic">
              <p className="ld-proof-label">{t.heroCard.readinessLabel}</p>
              <div>
                <div><span>{t.heroCard.roleReadiness}</span><strong>{t.heroCard.roleRange}</strong></div>
                <div><span>{t.heroCard.interviewReadiness}</span><strong>{t.heroCard.interviewRange}</strong></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="why" className="ld-section">
        <Reveal className="shell ld-section-grid">
          <div className="ld-section-head">
            <p className="ld-eyebrow mono">{t.problem.eyebrow}</p>
            <h2 className="ld-h2 display">{t.problem.title}</h2>
            <p className="ld-copy">{t.problem.body}</p>
          </div>
          <Reveal as="div" stagger className="ld-signal-grid">
            {t.problem.cards.map((card) => (
              <article key={card.title} className="ld-signal hover-lift">
                <h3>{card.title}</h3>
                <p>{card.body}</p>
                {card.href ? (
                  <a href={card.href} target="_blank" rel="noreferrer">
                    {card.source}
                  </a>
                ) : (
                  <span>{card.source}</span>
                )}
              </article>
            ))}
          </Reveal>
        </Reveal>
      </section>

      <section id="how-it-works" className="ld-section">
        <Reveal className="shell">
          <p className="ld-eyebrow mono">{t.how.eyebrow}</p>
          <h2 className="ld-h2 display">{t.how.title}</h2>
          <Reveal as="ol" stagger className="ld-method">
            {t.how.steps.map((step) => (
              <li key={step.n}>
                <b className="mono">{step.n}</b>
                <strong>{step.title}</strong>
                <span>{step.body}</span>
              </li>
            ))}
          </Reveal>
        </Reveal>
      </section>

      <Reveal as="section" className="ld-section">
        <div className="shell ld-two-col">
          <div className="ld-section-head">
            <p className="ld-eyebrow mono">{t.moment.eyebrow}</p>
            <h2 className="ld-h2 display">{t.moment.title}</h2>
            <p className="ld-copy">{t.moment.body}</p>
          </div>
          <div className="ld-ledger">
            <p className="ld-ledger-claim">{t.moment.story}</p>
            {t.moment.questions.map((question, index) => (
              <div key={question} className="ld-ledger-row">
                <span className="mono">0{index + 1}</span>
                <p>{question}</p>
              </div>
            ))}
          </div>
        </div>
      </Reveal>

      <Reveal as="section" className="ld-section">
        <div className="shell ld-two-col">
          <div className="ld-section-head">
            <p className="ld-eyebrow mono">{t.looksAt.eyebrow}</p>
            <h2 className="ld-h2 display">{t.looksAt.title}</h2>
          </div>
          <Reveal as="dl" stagger className="ld-dimensions">
            {t.looksAt.items.map((item, index) => (
              <div key={item}>
                <dt className="mono">{String(index + 1).padStart(2, "0")}</dt>
                <dd>
                  <strong>{item}</strong>
                </dd>
              </div>
            ))}
          </Reveal>
        </div>
      </Reveal>

      <Reveal as="section" className="ld-section">
        <div className="shell" id="sample-reflection">
          <p className="ld-eyebrow mono">{t.sample.eyebrow}</p>
          <div className="ld-diagnostic">
            <div>
              <span>{t.sample.roleReadiness}</span>
              <strong>{t.sample.roleRange}</strong>
              <small>{t.sample.roleNote}</small>
            </div>
            <div>
              <span>{t.sample.interviewReadiness}</span>
              <strong>{t.sample.interviewRange}</strong>
              <small>{t.sample.interviewNote}</small>
            </div>
            <div>
              <span>{t.sample.cameThroughLabel}</span>
              <b>{t.sample.cameThrough}</b>
            </div>
            <div>
              <span>{t.sample.nextLabel}</span>
              <b>{t.sample.next}</b>
            </div>
          </div>
        </div>
      </Reveal>

      <Reveal as="section" className="ld-section">
        <div className="shell">
          <p className="ld-eyebrow mono">{t.comparison.eyebrow}</p>
          <h2 className="ld-h2 display">{t.comparison.title}</h2>
          <div className="ld-comparison" role="table" aria-label={t.comparison.ariaLabel}>
            <div role="row" className="ld-comparison-head">
              {t.comparison.head.map((label) => (
                <span key={label}>{label}</span>
              ))}
            </div>
            {t.comparison.rows.map(([label, mirror, generic]) => (
              <div role="row" key={label} className="ld-comparison-row">
                <strong>{label}</strong>
                <span>{mirror}</span>
                <span>{generic}</span>
              </div>
            ))}
          </div>
        </div>
      </Reveal>

      <Reveal as="section" className="ld-section">
        <div className="shell ld-two-col">
          <div className="ld-section-head">
            <p className="ld-eyebrow mono">{t.trust.eyebrow}</p>
            <h2 className="ld-h2 display">{t.trust.title}</h2>
          </div>
          <Reveal as="ul" stagger className="ld-trust-list">
            {t.trust.points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </Reveal>
        </div>
      </Reveal>

      <Reveal as="section" className="ld-section ld-final">
        <div className="shell ld-final-inner">
          <div>
            <p className="ld-eyebrow mono">{t.final.eyebrow}</p>
            <h2 className="ld-h2 display">{t.final.title}</h2>
          </div>
          <div className="ld-hero-actions">
            <Link href="/signup" className="button-primary">
              {t.final.cta} <ArrowRight size={18} />
            </Link>
          </div>
        </div>
      </Reveal>

      <footer className="ld-footer">
        <div className="shell ld-footer-inner">
          <p>{t.footer}</p>
          <p>{meta.byline}</p>
        </div>
      </footer>
    </main>
  );
}
