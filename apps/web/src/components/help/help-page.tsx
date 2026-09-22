"use client";

import { ArrowRight } from "@phosphor-icons/react";

import { PageHeader, PageShell } from "@/components/workspace/page-shell";
import { help as t } from "@/lib/copy";

const SUPPORT_EMAIL = "support@pathwisse.com";

export function HelpPage() {
  return (
    <PageShell>
      <PageHeader eyebrow={t.eyebrow} title={t.title} intro={t.intro} />
      <div className="dh-home-sections">
        {t.sections.map((section) => (
          <section className="dh-section" key={section.title}>
            <h2 className="display">{section.title}</h2>
            <p className="dh-prose">{section.body}</p>
          </section>
        ))}
        <section className="dh-section">
          <h2 className="display">{t.contactLabel}</h2>
          <p className="dh-prose">{t.contact}</p>
          <a className="dh-text-action" href={`mailto:${SUPPORT_EMAIL}`}>
            {t.contactAction} <ArrowRight size={15} aria-hidden="true" />
          </a>
        </section>
      </div>
    </PageShell>
  );
}
