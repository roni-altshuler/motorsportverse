import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";

import Footer from "@/components/Footer";
import LiveContextBand from "@/components/race-weekend/LiveContextBand";
import Navbar from "@/components/Navbar";
import SmoothScrollProvider from "@/components/SmoothScrollProvider";
import { SeasonProvider } from "@/lib/SeasonProvider";

import "./globals.css";

// The exact RaceIQ F1 type system, so F3 reads as part of one product family:
// display = Saira Condensed (headlines + wordmark), body = EB Garamond (serif),
// labels/buttons/captions = JetBrains Mono. F3 keeps its own championship gold
// identity (--accent:#D9A441) — only the typefaces are shared with F1.
// Fonts are VENDORED, not fetched.
//
// `next/font/google` downloads the font files at BUILD time, so every
// production build depended on fonts.googleapis.com being reachable and a blip
// there failed it outright ("Error while requesting resource"). That is a
// network dependency inside a build that otherwise has none — this repo ships a
// fully static export from committed JSON, and the fonts were the one thing
// still phoning out. The files now live beside this layout and the build is
// hermetic.
//
// Same families, same weights, same latin subset as before. To change a weight,
// add the .woff2 under ./fonts/ and list it here — do not reintroduce the
// google import.
const saira = localFont({
  src: [
    { path: "./fonts/SairaCondensed-500.woff2", weight: "500", style: "normal" },
    { path: "./fonts/SairaCondensed-600.woff2", weight: "600", style: "normal" },
    { path: "./fonts/SairaCondensed-700.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-saira",
  display: "swap",
});
const garamond = localFont({
  src: [
    { path: "./fonts/EBGaramond-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/EBGaramond-500.woff2", weight: "500", style: "normal" },
    { path: "./fonts/EBGaramond-600.woff2", weight: "600", style: "normal" },
  ],
  variable: "--font-garamond",
  display: "swap",
});
const jetbrains = localFont({
  src: [
    { path: "./fonts/JetBrainsMono-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/JetBrainsMono-500.woff2", weight: "500", style: "normal" },
  ],
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
  title: "RaceIQ F3 — Formula 3 predictions",
  description:
    "Qualifying, sprint, feature-race, and championship forecasts for the FIA Formula 3 championship, from a model built for a spec series. A MotorsportVerse project on motorsport-core.",
  applicationName: "RaceIQ F3",
  manifest: MANIFEST_URL,
  appleWebApp: {
    capable: true,
    title: "RaceIQ F3",
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
    title: "RaceIQ F3 — Formula 3 predictions",
    description:
      "Sprint, feature-race, and championship forecasts for FIA Formula 3 — a MotorsportVerse project.",
    type: "website",
  },
  twitter: { card: "summary_large_image" },
};

// Theme-color + color-scheme for the browser chrome / PWA status bar. The app is
// dark-only; the championship-gold bar mirrors the manifest theme_color.
export const viewport: Viewport = {
  themeColor: "#D9A441",
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
