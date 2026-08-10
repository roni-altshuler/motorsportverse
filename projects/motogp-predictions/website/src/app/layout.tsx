import type { Metadata, Viewport } from "next";
import { EB_Garamond, JetBrains_Mono, Saira_Condensed } from "next/font/google";

import Footer from "@/components/Footer";
import LiveContextBand from "@/components/race-weekend/LiveContextBand";
import Navbar from "@/components/Navbar";
import SmoothScrollProvider from "@/components/SmoothScrollProvider";
import { SeasonProvider } from "@/lib/SeasonProvider";

import "./globals.css";

// The exact RaceIQ F1 type system, so MotoGP reads as part of one product family:
// display = Saira Condensed (headlines + wordmark), body = EB Garamond (serif),
// labels/buttons/captions = JetBrains Mono. MotoGP keeps its own red brand
// identity (--accent:#CC0000) — only the typefaces are shared with F1.
const saira = Saira_Condensed({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-saira",
  display: "swap",
});
const garamond = EB_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-garamond",
  display: "swap",
});
const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-jetbrains",
  display: "swap",
});

// PWA "add to home screen": manifest + icon set live in public/ and are served
// under the deploy base path. The manifest itself uses base-path-relative URLs
// (start_url/scope/icons) so it resolves correctly whether the site is deployed
// at the domain root or under a Pages subpath. No service worker is registered —
// the site is a fully static export and stays offline-safe.
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";
const MANIFEST_URL = `${BASE_PATH}/manifest.webmanifest`;
const APPLE_TOUCH_ICON = `${BASE_PATH}/icons/apple-touch-icon.png`;
const ICON_192 = `${BASE_PATH}/icons/icon-192.png`;
const ICON_512 = `${BASE_PATH}/icons/icon-512.png`;

export const metadata: Metadata = {
  title: "MotoGP Predictions — RaceIQ MotoGP",
  description:
    "Sprint, Grand Prix, and championship forecasts for the premier class of motorcycle Grand Prix racing — rider and manufacturer title fights, updated every round. A MotorsportVerse project on motorsport-core.",
  applicationName: "RaceIQ MotoGP",
  manifest: MANIFEST_URL,
  appleWebApp: {
    capable: true,
    title: "RaceIQ MotoGP",
    statusBarStyle: "black-translucent",
  },
  icons: {
    icon: [
      { url: ICON_192, sizes: "192x192", type: "image/png" },
      { url: ICON_512, sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: APPLE_TOUCH_ICON, sizes: "180x180", type: "image/png" }],
  },
  openGraph: {
    title: "MotoGP Predictions — RaceIQ MotoGP",
    description:
      "Sprint, Grand Prix, and championship forecasts for MotoGP — a MotorsportVerse project.",
    type: "website",
  },
  twitter: { card: "summary_large_image" },
};

// Theme-color + color-scheme for the browser chrome / PWA status bar. The app is
// dark-only; the MotoGP-red bar mirrors the manifest theme_color.
export const viewport: Viewport = {
  themeColor: "#CC0000",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      data-theme="dark"
      suppressHydrationWarning
      className={`${saira.variable} ${garamond.variable} ${jetbrains.variable}`}
    >
      <body className="min-h-screen w-full flex flex-col antialiased">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:bg-[color:var(--ink)] focus:px-3 focus:py-2 focus:text-[color:var(--canvas)]"
        >
          Skip to main content
        </a>
        <SeasonProvider>
          <SmoothScrollProvider>
            <Navbar />
            <LiveContextBand />
            <main id="main-content" tabIndex={-1} className="flex-1 w-full min-h-[70vh]">
              {children}
            </main>
            <Footer />
          </SmoothScrollProvider>
        </SeasonProvider>
      </body>
    </html>
  );
}
