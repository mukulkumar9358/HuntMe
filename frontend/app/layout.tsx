import "@fontsource-variable/bricolage-grotesque";
import "@fontsource-variable/hanken-grotesk";
import type { Metadata, Viewport } from "next";

import { Providers } from "@/components/common/Providers";
import { SiteHeader } from "@/components/layout/SiteHeader";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "HuntMe: Hide. Hunt. Prove it.", template: "%s | HuntMe" },
  description: "Real-world multiplayer hide-and-seek. Pick a place, split into two teams, and find each other with a Hot & Cold radar.",
  applicationName: "HuntMe",
};

export const viewport: Viewport = { themeColor: "#080d19", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-dvh">
        <Providers>
          <SiteHeader />
          <main>{children}</main>
        </Providers>
      </body>
    </html>
  );
}
