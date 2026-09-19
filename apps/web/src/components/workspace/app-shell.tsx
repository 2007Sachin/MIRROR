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

import "@/styles/workspace.css";

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
    <div className="app-shell ws-shell">
      <aside className="ws-sidebar" aria-label="Primary navigation">
        <Link href="/dashboard" className="ws-brand" aria-label="Mirror home">
          <Image src="/icon.svg" alt="" width={24} height={24} priority />
          <span>MIRROR</span>
        </Link>

        <nav className="ws-nav">
          {navigation.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`));
            return (
              <Link
                key={href}
                href={href}
                className={`ws-nav-item${active ? " is-active" : ""}`}
                aria-current={active ? "page" : undefined}
              >
                <Icon size={18} weight={active ? "fill" : "regular"} />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="ws-sidebar-account">
          <div className="ws-avatar" aria-hidden="true">{initials(profile)}</div>
          <div className="ws-account-info">
            <strong>{profile?.full_name || "Mirror candidate"}</strong>
            <span>{profile?.email || "Private workspace"}</span>
          </div>
          <button type="button" className="ws-logout" onClick={() => void logout()} aria-label="Log out">
            <SignOut size={17} />
          </button>
        </div>
      </aside>

      <div className="ws-main">
        <header className="ws-topbar">
          <Link href="/dashboard" className="ws-topbar-brand" aria-label="Mirror home">
            <Image src="/icon.svg" alt="" width={22} height={22} priority />
            <span>MIRROR</span>
          </Link>
          <p className="ws-topbar-label">Evidence workspace</p>
          <Link href="/settings" className="ws-topbar-user" aria-label="Open account settings">
            <span>{initials(profile)}</span>
            <strong>{profile?.full_name || "Your account"}</strong>
          </Link>
        </header>

        {logoutError ? <div className="ws-alert" role="alert">{logoutError}</div> : null}
        <main id="main-content" className="ws-content">{children}</main>
      </div>

      <nav className="ws-mobile-nav" aria-label="Mobile navigation">
        {navigation.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`));
          return (
            <Link
              key={href}
              href={href}
              className={`ws-mobile-nav-item${active ? " is-active" : ""}`}
              aria-current={active ? "page" : undefined}
            >
              <Icon size={19} weight={active ? "fill" : "regular"} />
              <span>{label === "Evidence Library" ? "Evidence" : label.replace(" Explorer", "")}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
