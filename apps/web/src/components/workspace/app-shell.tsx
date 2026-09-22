"use client";

import {
  BookOpenText,
  CaretDown,
  ChartLineUp,
  ChatCircleText,
  Compass,
  FileText,
  Gear,
  House,
  List,
  Question,
  SignOut,
  User,
  X,
} from "@phosphor-icons/react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

import type { Profile } from "@/lib/api";
import { profileMenu as menuCopy } from "@/lib/copy";
import { getSupabaseBrowserClient } from "@/lib/supabase";

import "@/styles/workspace.css";

const primaryNavigation = [
  { href: "/dashboard", label: "Home", mobileLabel: "Home", icon: House },
  { href: "/practice", label: "Practice", mobileLabel: "Practice", icon: ChatCircleText },
  { href: "/stories", label: "My Stories", mobileLabel: "Stories", icon: BookOpenText },
  { href: "/experience", label: "My Experience", mobileLabel: "Experience", icon: FileText },
  { href: "/roles", label: "Roles", mobileLabel: "Roles", icon: Compass },
  { href: "/progress", label: "Progress", mobileLabel: "Progress", icon: ChartLineUp },
] as const;

const secondaryNavigation = [
  { href: "/settings", label: "Settings", icon: Gear },
  { href: "/help", label: "Help", icon: Question },
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

export function AppShell({ children, profile }: { children: ReactNode; profile: Profile | null }) {
  const pathname = usePathname();
  const router = useRouter();
  const [logoutError, setLogoutError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  function activeFor(href: string) {
    return pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`));
  }

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
        aria-label="Close navigation"
        onClick={() => setSidebarOpen(false)}
      />
      <aside id="workspace-navigation" className={`ws-sidebar${sidebarOpen ? " is-open" : ""}`} aria-label="Primary navigation">
        <div className="ws-sidebar-head">
          <Link href="/dashboard" className="ws-brand" aria-label="Mirror home" onClick={() => setSidebarOpen(false)}>
            <Image src="/icon.svg" alt="" width={24} height={24} priority />
            <span>MIRROR</span>
          </Link>
          <button type="button" className="ws-sidebar-close" onClick={() => setSidebarOpen(false)} aria-label="Close navigation">
            <X size={19} aria-hidden="true" />
          </button>
        </div>

        <nav className="ws-nav" aria-label="Workspace">
          {primaryNavigation.map(({ href, label, icon: Icon }) => {
            const active = activeFor(href);
            return (
              <Link key={href} href={href} className={`ws-nav-item${active ? " is-active" : ""}`} aria-current={active ? "page" : undefined} onClick={() => setSidebarOpen(false)}>
                <Icon size={18} weight={active ? "fill" : "regular"} aria-hidden="true" />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>

        <nav className="ws-nav ws-nav-secondary" aria-label="Support and settings">
          {secondaryNavigation.map(({ href, label, icon: Icon }) => {
            const active = activeFor(href);
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
              <strong>{profile?.full_name || "Mirror member"}</strong>
              <span>{profile?.email || "Private workspace"}</span>
            </span>
          </Link>
          <button type="button" className="ws-logout" onClick={() => void logout()} aria-label={menuCopy.signOut}>
            <SignOut size={17} aria-hidden="true" />
          </button>
        </div>
      </aside>

      <div className="ws-main">
        <header className="ws-topbar">
          <div className="ws-topbar-start">
            <button type="button" className="ws-menu-button" aria-label="Open navigation" aria-controls="workspace-navigation" aria-expanded={sidebarOpen} onClick={() => setSidebarOpen(true)}>
              <List size={20} aria-hidden="true" />
            </button>
            <Link href="/dashboard" className="ws-topbar-brand" aria-label="Mirror home">
              <Image src="/icon.svg" alt="" width={22} height={22} priority />
              <span>MIRROR</span>
            </Link>
          </div>
          <div className="ws-topbar-actions">
            <Link href="/help" className="ws-topbar-help"><Question size={17} aria-hidden="true" /><span>Help</span></Link>
            <ProfileMenu profile={profile} onSignOut={logout} />
          </div>
        </header>

        {logoutError ? <div className="ws-alert" role="alert">{logoutError}</div> : null}
        <main id="main-content" className="ws-content">{children}</main>
      </div>

      <nav className="ws-mobile-nav" aria-label="Mobile navigation">
        {primaryNavigation.map(({ href, mobileLabel, icon: Icon }) => {
          const active = activeFor(href);
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
 * A short menu for the account only. The main navigation is not repeated here:
 * everything in it already has a permanent home in the sidebar.
 */
function ProfileMenu({ profile, onSignOut }: { profile: Profile | null; onSignOut: () => Promise<void> }) {
  const container = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);

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
        onClick={() => setOpen((value) => !value)}
      >
        <span aria-hidden="true">{initials(profile)}</span>
        <strong>{profile?.full_name || menuCopy.open}</strong>
        <CaretDown size={13} aria-hidden="true" />
      </button>
      {open ? (
        <div className="ws-profile-panel" role="menu" aria-label={menuCopy.open}>
          <div className="ws-profile-identity">
            <strong>{profile?.full_name || "Mirror member"}</strong>
            <span>{profile?.email || "Private workspace"}</span>
          </div>
          <Link role="menuitem" href="/settings#profile" onClick={() => setOpen(false)}>
            <User size={16} aria-hidden="true" /> {menuCopy.profile}
          </Link>
          <Link role="menuitem" href="/settings#interview" onClick={() => setOpen(false)}>
            <ChatCircleText size={16} aria-hidden="true" /> {menuCopy.preferences}
          </Link>
          <Link role="menuitem" href="/settings#account" onClick={() => setOpen(false)}>
            <Gear size={16} aria-hidden="true" /> {menuCopy.account}
          </Link>
          <hr />
          <Link role="menuitem" href="/help" onClick={() => setOpen(false)}>
            <Question size={16} aria-hidden="true" /> {menuCopy.help}
          </Link>
          <button role="menuitem" type="button" onClick={() => void onSignOut()}>
            <SignOut size={16} aria-hidden="true" /> {menuCopy.signOut}
          </button>
        </div>
      ) : null}
    </div>
  );
}
