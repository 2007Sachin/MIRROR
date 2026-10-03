"use client";

import {
  BookOpenText,
  CaretDown,
  ChatCircleText,
  Compass,
  FileText,
  Gear,
  House,
  List,
  MapTrifold,
  Notebook,
  Question,
  X,
} from "@phosphor-icons/react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

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
  const [sidebarOpen, setSidebarOpen] = useState(false);

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
      <button
        type="button"
        className={`ws-sidebar-backdrop${sidebarOpen ? " is-visible" : ""}`}
        aria-label={shellCopy.closeNav}
        onClick={() => setSidebarOpen(false)}
      />
      <aside id="workspace-navigation" className={`ws-sidebar${sidebarOpen ? " is-open" : ""}`} aria-label={shellCopy.primaryNav}>
        <div className="ws-sidebar-head">
          <Link href="/dashboard" className="ws-brand" aria-label={shellCopy.homeLink} onClick={() => setSidebarOpen(false)}>
            <Image src="/icon.svg" alt="" width={24} height={24} priority />
            <span>MIRROR</span>
          </Link>
          <button type="button" className="ws-sidebar-close" onClick={() => setSidebarOpen(false)} aria-label={shellCopy.closeNav}>
            <X size={19} aria-hidden="true" />
          </button>
        </div>

        <nav className="ws-nav" aria-label={shellCopy.primaryNav}>
          {primaryNavigation.map(({ href, label, icon: Icon, match }) => {
            const active = activeFor(match);
            return (
              <Link key={href} href={href} className={`ws-nav-item${active ? " is-active" : ""}`} aria-current={active ? "page" : undefined} onClick={() => setSidebarOpen(false)}>
                <Icon size={18} weight={active ? "fill" : "regular"} aria-hidden="true" />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="ws-sidebar-account">
          <Link href="/settings" className="ws-account-link" onClick={() => setSidebarOpen(false)}>
            <span className="ws-avatar" aria-hidden="true">{initials(profile)}</span>
            <span className="ws-account-info">
              <strong>{profile?.full_name || shellCopy.memberFallback}</strong>
              <span>{profile?.email || shellCopy.emailFallback}</span>
            </span>
          </Link>
        </div>
      </aside>

      <div className="ws-main">
        <header className="ws-topbar">
          <div className="ws-topbar-start">
            <button type="button" className="ws-menu-button" aria-label={shellCopy.openNav} aria-controls="workspace-navigation" aria-expanded={sidebarOpen} onClick={() => setSidebarOpen(true)}>
              <List size={20} aria-hidden="true" />
            </button>
            <Link href="/dashboard" className="ws-topbar-brand" aria-label={shellCopy.homeLink}>
              <Image src="/icon.svg" alt="" width={22} height={22} priority />
              <span>MIRROR</span>
            </Link>
            <RoleSwitcher />
          </div>
          <div className="ws-topbar-actions">
            <ProfileMenu profile={profile} onSignOut={logout} />
          </div>
        </header>

        {logoutError ? <div className="ws-alert" role="alert">{logoutError}</div> : null}
        <main id="main-content" className="ws-content">{children}</main>
      </div>

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
    </div>
  );
}

/**
 * The profile menu holds everything that is not a primary destination: experience,
 * roles, preferences, help, and a labelled Sign out.
 */
function ProfileMenu({ profile, onSignOut }: { profile: Profile | null; onSignOut: () => Promise<void> }) {
  const container = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
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
    <div className="ws-profile-menu" ref={container}>
      <button
        ref={trigger}
        type="button"
        className="ws-topbar-user"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={name === menuCopy.open ? name : `${menuCopy.open}: ${name}`}
        onClick={() => setOpen((value) => !value)}
      >
        <span aria-hidden="true">{initials(profile)}</span>
        <strong>{name}</strong>
        <CaretDown size={13} aria-hidden="true" />
      </button>
      {open ? (
        <div className="ws-profile-panel" role="menu" aria-label={menuCopy.open}>
          <div className="ws-profile-identity">
            <strong>{profile?.full_name || shellCopy.memberFallback}</strong>
            <span>{profile?.email || shellCopy.emailFallback}</span>
          </div>
          {profileNavigation.map(({ href, label, icon: Icon }) => (
            <Link key={href} role="menuitem" href={href} onClick={() => setOpen(false)}>
              <Icon size={16} aria-hidden="true" /> {label}
            </Link>
          ))}
          <hr />
          <button role="menuitem" type="button" className="ws-signout" onClick={() => void onSignOut()}>
            {menuCopy.signOut}
          </button>
        </div>
      ) : null}
    </div>
  );
}
