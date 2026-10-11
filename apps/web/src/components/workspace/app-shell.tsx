"use client";

import {
  BookOpenText,
  CaretDown,
  ChatCircleText,
  Compass,
  FileText,
  Gear,
  House,
  MapTrifold,
  Notebook,
  Plus,
  Question,
} from "@phosphor-icons/react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import type { Profile } from "@/lib/api";
import { profileMenu as menuCopy } from "@/lib/copy";
import { shellCopy } from "@/lib/copy-shell";
import { getSupabaseBrowserClient } from "@/lib/supabase";

import { RoleSwitcher } from "./role-switcher";

import "@/styles/workspace.css";

/** A path is active when it equals a prefix or sits under it; a RegExp matches the whole path. */
type Match = string | RegExp;

// Role pages (/roles/<id>/...) are part of My plan; the role list and /roles/new are not.
const ROLE_PAGE = /^\/roles\/(?!new(?:\/|$))[^/]+(?:\/|$)/;

const primaryNavigation = [
  { href: "/dashboard", ...shellCopy.nav.home, icon: House, match: ["/dashboard"] as Match[] },
  { href: "/plan", ...shellCopy.nav.plan, icon: MapTrifold, match: ["/plan", ROLE_PAGE] as Match[] },
  { href: "/stories", ...shellCopy.nav.stories, icon: BookOpenText, match: ["/stories"] as Match[] },
  { href: "/practice", ...shellCopy.nav.practice, icon: ChatCircleText, match: ["/practice"] as Match[] },
  { href: "/reflect", ...shellCopy.nav.reflect, icon: Notebook, match: ["/reflect", "/progress"] as Match[] },
];

const profileNavigation = [
  { href: "/experience", ...shellCopy.profile.experience, icon: FileText },
  { href: "/roles", ...shellCopy.profile.roles, icon: Compass },
  { href: "/settings", ...shellCopy.profile.preferences, icon: Gear },
  { href: "/help", ...shellCopy.profile.help, icon: Question },
];

function matches(pathname: string, match: Match) {
  if (typeof match !== "string") return match.test(pathname);
  return pathname === match || pathname.startsWith(`${match}/`);
}

function initials(profile: Profile | null) {
  const source = profile?.full_name || profile?.email || "Mirror user";
  return source
    .split(/\s+|@/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function AppShell({ children, profile }: { children: ReactNode; profile: Profile | null }) {
  const pathname = usePathname();
  const router = useRouter();
  const [logoutError, setLogoutError] = useState("");

  const activeFor = (match: Match[]) => match.some((item) => matches(pathname, item));

  async function logout() {
    setLogoutError("");
    const { error } = await getSupabaseBrowserClient().auth.signOut();
    if (error) {
      setLogoutError(menuCopy.signOutFailed);
      return;
    }
    router.replace("/login");
    router.refresh();
  }

  return (
    <div className="app-shell ws-shell">
      {/* Glass top bar. One navigation list drives both this bar (wide screens) and the tab bar (narrow screens). */}
      <header className="ws-topbar">
        <Link href="/dashboard" className="ws-brand" aria-label={shellCopy.homeLink}>
          <Image src="/icon.svg" alt="" width={22} height={22} priority />
          <span>MIRROR</span>
        </Link>
        <nav className="ws-nav" aria-label={shellCopy.primaryNav}>
          {primaryNavigation.map(({ href, label, match }) => {
            const active = activeFor(match);
            return (
              <Link key={href} href={href} className={`ws-nav-item${active ? " is-active" : ""}`} aria-current={active ? "page" : undefined}>
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="ws-topbar-actions">
          <RoleSwitcher />
          <ProfileMenu profile={profile} onSignOut={logout} />
        </div>
      </header>

      {/* The tab bar is fixed to the bottom but sits before <main> so keyboard and screen-reader users reach it first. */}
      <nav className="ws-mobile-nav" aria-label={shellCopy.mobileNav}>
        {primaryNavigation.map(({ href, mobileLabel, icon: Icon, match }) => {
          const active = activeFor(match);
          return (
            <Link key={href} href={href} className={`ws-mobile-nav-item${active ? " is-active" : ""}`} aria-current={active ? "page" : undefined}>
              <Icon size={19} weight={active ? "fill" : "regular"} aria-hidden="true" />
              <span>{mobileLabel}</span>
            </Link>
          );
        })}
      </nav>

      {logoutError ? <div className="ws-alert" role="alert">{logoutError}</div> : null}
      <main id="main-content" className="ws-content">{children}</main>
    </div>
  );
}

/**
 * The profile menu holds everything that is not a primary destination: experience,
 * roles, preferences, help, and a labelled Sign out. It is a disclosure (a button that
 * shows a panel of ordinary links), so Tab moves through it and leaving it closes it.
 */
function ProfileMenu({ profile, onSignOut }: { profile: Profile | null; onSignOut: () => Promise<void> }) {
  const container = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const [open, setOpen] = useState(false);
  const name = profile?.full_name || menuCopy.open;

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      trigger.current?.focus();
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  return (
    <div
      className="ws-profile-menu"
      ref={container}
      onBlur={(event) => {
        if (!container.current?.contains(event.relatedTarget as Node | null)) setOpen(false);
      }}
    >
      <button
        ref={trigger}
        type="button"
        className="ws-topbar-user"
        aria-controls={panelId}
        aria-expanded={open}
        aria-label={name === menuCopy.open ? name : `${menuCopy.open}: ${name}`}
        onClick={() => setOpen((value) => !value)}
      >
        <span aria-hidden="true">{initials(profile)}</span>
        <strong>{name}</strong>
        <CaretDown size={13} aria-hidden="true" />
      </button>
      {open ? (
        <div className="ws-profile-panel" id={panelId}>
          <div className="ws-profile-identity">
            <strong>{profile?.full_name || shellCopy.memberFallback}</strong>
            <span>{profile?.email || shellCopy.emailFallback}</span>
          </div>
          {profileNavigation.map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href} onClick={() => setOpen(false)}>
              <Icon size={16} aria-hidden="true" /> {label}
            </Link>
          ))}
          {/* The top bar hides "Add a role" on small screens, so it lives here there. */}
          <Link href="/roles/new" className="ws-profile-narrow-only" onClick={() => setOpen(false)}>
            <Plus size={16} aria-hidden="true" /> {shellCopy.roleSwitcher.addRole}
          </Link>
          <hr />
          <button type="button" className="ws-signout" onClick={() => void onSignOut()}>
            {menuCopy.signOut}
          </button>
        </div>
      ) : null}
    </div>
  );
}
