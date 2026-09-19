import { ArrowRight, Briefcase, FilePlus, MagnifyingGlass } from "@phosphor-icons/react";
import Link from "next/link";

const actions = [
  {
    href: "/diagnostics",
    title: "View past diagnostics",
    copy: "Revisit your findings and track progress.",
    icon: Briefcase,
  },
  {
    href: "/evidence",
    title: "Add or update evidence",
    copy: "Upload new documents, projects or achievements.",
    icon: FilePlus,
  },
  {
    href: "/roles",
    title: "Explore new roles",
    copy: "See role benchmarks and understand what's in demand.",
    icon: MagnifyingGlass,
  },
] as const;

export function QuickActions() {
  return (
    <section className="ws-panel" aria-labelledby="quick-actions-title">
      <div className="ws-section-heading">
        <div>
          <h2 id="quick-actions-title">Continue building your case</h2>
          <p>Choose the next useful step for your evidence.</p>
        </div>
      </div>
      <div className="ws-action-list">
        {actions.map(({ href, title, copy, icon: Icon }) => (
          <Link key={href} href={href} className="ws-action-item">
            <span><Icon size={19} /></span>
            <div><strong>{title}</strong><p>{copy}</p></div>
            <ArrowRight size={15} />
          </Link>
        ))}
      </div>
    </section>
  );
}
