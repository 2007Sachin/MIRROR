import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { meta } from "@/lib/copy";
import "./globals.css";

export const metadata: Metadata = {
  title: meta.title,
  description: meta.description,
  manifest: "/manifest.webmanifest",
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = { themeColor: "#F7F5EE", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>
        <a href="#main-content" className="skip-link">{meta.skipLink}</a>
        <header className="site-header shell flex h-16 items-center justify-between border-b hairline">
          <Link href="/" className="display text-lg font-semibold tracking-[-0.03em]">Mirror</Link>
          <span className="text-xs text-[var(--silver)]">{meta.byline}</span>
        </header>
        {children}
      </body>
    </html>
  );
}
