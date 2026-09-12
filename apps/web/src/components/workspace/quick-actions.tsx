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
    <section className="dashboard-quick-actions app-panel" aria-labelledby="quick-actions-title">
      <div className="app-section-heading">
        <div>
          <h2 id="quick-actions-title">Continue building your case</h2>
          <p>Choose the next useful step for your evidence.</p>
        </div>
      </div>
      <div className="dashboard-action-list">
        {actions.map(({ href, title, copy, icon: Icon }) => (
          <Link key={href} href={href}>
            <span><Icon size={20} /></span>
            <div><strong>{title}</strong><p>{copy}</p></div>
            <ArrowRight size={16} />
          </Link>
        ))}
      </div>
    </section>
  );
}
