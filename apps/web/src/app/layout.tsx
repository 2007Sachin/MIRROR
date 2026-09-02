import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mirror by Pathwisse",
  description: "An evidence-backed interview diagnostic and claims audit.",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = { themeColor: "#10120F", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header className="shell flex h-16 items-center justify-between border-b hairline">
          <Link href="/" className="display text-lg font-semibold tracking-[-0.03em]">Mirror</Link>
          <span className="text-xs text-[var(--silver)]">by Pathwisse</span>
        </header>
        {children}
      </body>
    </html>
  );
}


