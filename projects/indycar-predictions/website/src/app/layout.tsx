import type { Metadata, Viewport } from "next";
import { EB_Garamond, JetBrains_Mono, Saira_Condensed } from "next/font/google";

import Footer from "@/components/Footer";
import LiveContextBand from "@/components/race-weekend/LiveContextBand";
import Navbar from "@/components/Navbar";
import SmoothScrollProvider from "@/components/SmoothScrollProvider";
import { SeasonProvider } from "@/lib/SeasonProvider";

import "./globals.css";

// The exact RaceIQ F1 type system, so IndyCar reads as part of one product
// family: display = Saira Condensed (headlines + wordmark), body = EB Garamond
// (serif), labels/buttons/captions = JetBrains Mono. IndyCar keeps its own
// racing-red identity (--accent:#D31217) — only the typefaces are shared
// with F1.
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

// PWA "add to home screen": the manifest + brand mark live in public/ and are
// served under the deploy base path. The manifest uses base-path-relative URLs
// (start_url/scope/icons) so it resolves correctly whether the site is deployed
// at the domain root or under a GitHub Pages subpath. No service worker is
// registered — the site is a fully static export and stays offline-safe.
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";
const MANIFEST_URL = `${BASE_PATH}/manifest.webmanifest`;
const BRAND_MARK = `${BASE_PATH}/brand/mark.svg`;

export const metadata: Metadata = {
  title: "RaceIQ Indy — NTT IndyCar Series predictions",
  description:
    "Race and championship forecasts for the NTT IndyCar Series — every round from street circuits to the Indianapolis 500, calibrated on real results. A MotorsportVerse project on motorsport-core.",
  manifest: MANIFEST_URL,
  applicationName: "RaceIQ Indy",
  appleWebApp: {
    capable: true,
    title: "RaceIQ Indy",
    statusBarStyle: "black-translucent",
  },
  icons: {
    icon: [{ url: BRAND_MARK, type: "image/svg+xml" }],
    apple: [{ url: BRAND_MARK, type: "image/svg+xml" }],
  },
  openGraph: {
    title: "RaceIQ Indy — NTT IndyCar Series predictions",
    description:
      "Race and championship forecasts for the NTT IndyCar Series — a MotorsportVerse project.",
    type: "website",
  },
  twitter: { card: "summary_large_image" },
};

// Theme-color + color-scheme for the browser chrome / PWA status bar. The app
// is dark-only; the IndyCar-red bar mirrors the manifest theme_color.
export const viewport: Viewport = {
  themeColor: "#D31217",
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
