import Link from "next/link";

import { roleWorkspace as t } from "@/lib/copy";

/** The parts of a role workspace. Real links, so each has its own address. */
export function RoleTabs({ roleProfileId, current }: { roleProfileId: string; current: "map" | "pressure" | "interviews" }) {
  const tabs = [
    { key: "map", href: `/roles/${roleProfileId}`, label: t.map },
    { key: "pressure", href: `/roles/${roleProfileId}/pressure-test`, label: t.pressure },
    { key: "interviews", href: `/roles/${roleProfileId}/interviews`, label: t.interviews },
  ] as const;
  return (
    <nav className="dh-role-tabs" aria-label={t.label}>
      {tabs.map((tab) => (
        <Link key={tab.key} href={tab.href} aria-current={tab.key === current ? "page" : undefined}>
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}
