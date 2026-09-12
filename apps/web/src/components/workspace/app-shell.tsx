"use client";

import {
  Briefcase,
  Compass,
  FileText,
  Gear,
  House,
  SignOut,
} from "@phosphor-icons/react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import type { Profile } from "@/lib/api";
import { getSupabaseBrowserClient } from "@/lib/supabase";

const navigation = [
  { href: "/dashboard", label: "Home", icon: House },
  { href: "/diagnostics", label: "Diagnostics", icon: Briefcase },
  { href: "/evidence", label: "Evidence Library", icon: FileText },
  { href: "/roles", label: "Role Explorer", icon: Compass },
  { href: "/settings", label: "Settings", icon: Gear },
] as const;

function initials(profile: Profile | null) {
  const source = profile?.full_name || profile?.email || "Mirror user";
  return source
    .split(/\s+|@/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function AppShell({
  children,
  profile,
}: {
  children: ReactNode;
  profile: Profile | null;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [logoutError, setLogoutError] = useState("");

  async function logout() {
    setLogoutError("");
    const { error } = await getSupabaseBrowserClient().auth.signOut();
    if (error) {
      setLogoutError("Mirror could not sign you out. Please try again.");
      return;
    }
    router.replace("/login");
    router.refresh();
  }

  return (
    <main className="app-workspace">
      <aside className="app-sidebar" aria-label="Primary navigation">
        <Link href="/dashboard" className="app-wordmark" aria-label="Mirror home">
          <Image src="/icon.svg" alt="" width={27} height={27} priority />
          <span>MIRROR</span>
        </Link>

        <nav className="app-sidebar-nav">
          {navigation.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`));
            return (
              <Link key={href} href={href} className={active ? "is-active" : ""} aria-current={active ? "page" : undefined}>
                <Icon size={19} weight={active ? "fill" : "regular"} />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="app-sidebar-account">
          <div className="app-avatar" aria-hidden="true">{initials(profile)}</div>
          <div>
            <strong>{profile?.full_name || "Mirror candidate"}</strong>
            <span>{profile?.email || "Private workspace"}</span>
          </div>
          <button type="button" onClick={() => void logout()} aria-label="Log out">
            <SignOut size={18} />
          </button>
        </div>
      </aside>

      <section className="app-workspace-main">
        <header className="app-topbar">
          <Link href="/dashboard" className="app-mobile-brand" aria-label="Mirror home">
            <Image src="/icon.svg" alt="" width={25} height={25} priority />
            <span>MIRROR</span>
          </Link>
          <p>Evidence workspace</p>
          <div>
            <Link href="/settings" className="app-topbar-user" aria-label="Open account settings">
              <span>{initials(profile)}</span>
              <strong>{profile?.full_name || "Your account"}</strong>
            </Link>
          </div>
        </header>

        {logoutError ? <div className="app-shell-alert" role="alert">{logoutError}</div> : null}
        <div className="app-content">{children}</div>
      </section>

      <nav className="app-mobile-nav" aria-label="Mobile navigation">
        {navigation.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`));
          return (
            <Link key={href} href={href} className={active ? "is-active" : ""} aria-current={active ? "page" : undefined}>
              <Icon size={19} weight={active ? "fill" : "regular"} />
              <span>{label === "Evidence Library" ? "Evidence" : label.replace(" Explorer", "")}</span>
            </Link>
          );
        })}
      </nav>
    </main>
  );
}
