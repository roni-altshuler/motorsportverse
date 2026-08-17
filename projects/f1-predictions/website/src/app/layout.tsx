import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import LiveContextBand from "@/components/race-weekend/LiveContextBand";
import SmoothScrollProvider from "@/components/SmoothScrollProvider";
import { SeasonProvider } from "@/lib/SeasonProvider";
import { DEFAULT_SEASON_YEAR } from "@/lib/season";

// Bugatti redesign uses the recommended open-source substitutes for the three
// licensed Bugatti typefaces: Saira Condensed (display headlines + wordmark),
// EB Garamond (serif body), JetBrains Mono (buttons + nav + captions). All at
// weight 400 — Bugatti's system has no bold role.
// Fonts are VENDORED, not fetched.
//
// `next/font/google` downloads the font files at BUILD time, so every
// production build depended on fonts.googleapis.com being reachable and a blip
// there failed it outright ("Error while requesting resource"). That is a
// network dependency inside a build that otherwise has none — this site is a
// fully static export from committed JSON, and the fonts were the one thing
// still phoning out. The files now live beside this layout, so the build is
// hermetic.
//
// Same families, same weights, same latin subset as before. Note the flagship
// uses a DIFFERENT weight set from the series sites (400/700 display, 400 for
// body and mono — Bugatti's system has no bold role), which is why only the
// weights listed here are vendored rather than the shared five.
const sairaCondensed = localFont({
  src: [
    { path: "./fonts/SairaCondensed-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/SairaCondensed-700.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-saira-condensed",
  display: "swap",
});

const ebGaramond = localFont({
  src: [{ path: "./fonts/EBGaramond-400.woff2", weight: "400", style: "normal" }],
  variable: "--font-eb-garamond",
  display: "swap",
});

const jetbrainsMono = localFont({
  src: [{ path: "./fonts/JetBrainsMono-400.woff2", weight: "400", style: "normal" }],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

const ACTIVE_SEASON_YEAR = String(DEFAULT_SEASON_YEAR);

// Public site URL — used by Next.js to absolutize OG / Twitter image URLs.
// Falls back to the GitHub Pages URL for this repo. Override locally with
// `NEXT_PUBLIC_SITE_URL=http://localhost:3000` if you want absolute URLs in dev.
const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ||
  "https://roni-altshuler.github.io/f1_predictions";

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";
const OG_DEFAULT = `${BASE_PATH}/og/default.png`;

// PWA "add to home screen": manifest + icon set live in public/ and are served
// under the deploy base path. The manifest itself uses base-path-relative URLs
// (start_url/scope/icons) so it resolves correctly whether the site is deployed
// at the domain root or under a GitHub Pages subpath. No service worker is
// registered — the site is a fully static export and stays offline-safe.
const MANIFEST_URL = `${BASE_PATH}/manifest.webmanifest`;
const APPLE_TOUCH_ICON = `${BASE_PATH}/icons/apple-touch-icon.png`;
const ICON_192 = `${BASE_PATH}/icons/icon-192.png`;
const ICON_512 = `${BASE_PATH}/icons/icon-512.png`;

const SITE_TITLE = `RaceIQ | F1 ${ACTIVE_SEASON_YEAR} Race Predictions & Forecasts`;
const SITE_DESCRIPTION =
  `AI and machine learning-powered Formula 1 ${ACTIVE_SEASON_YEAR} season predictions. ` +
  "Race classifications, championship standings, pit strategy simulations, " +
  "and professional visualizations for every Grand Prix.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: SITE_TITLE,
  description: SITE_DESCRIPTION,
  manifest: MANIFEST_URL,
  applicationName: "RaceIQ",
  appleWebApp: {
    capable: true,
    title: "RaceIQ",
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
    type: "website",
    siteName: "RaceIQ",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    url: "/",
    images: [
      {
        url: OG_DEFAULT,
        width: 1200,
        height: 630,
        alt: `RaceIQ — F1 ${ACTIVE_SEASON_YEAR} AI-powered race forecasts`,
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    images: [OG_DEFAULT],
  },
};

// Theme-color + color-scheme for the browser chrome / PWA status bar. The app
// is dark-only (broadcast HUD); the F1-red bar echoes the accent stripe used
// across the OG share cards and mirrors the manifest theme_color.
export const viewport: Viewport = {
  themeColor: "#E10600",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      data-theme="dark"
      suppressHydrationWarning
      className={`${sairaCondensed.variable} ${ebGaramond.variable} ${jetbrainsMono.variable}`}
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
            <main id="main-content" tabIndex={-1} className="flex-1 w-full">{children}</main>
            <Footer />
          </SmoothScrollProvider>
        </SeasonProvider>
      </body>
    </html>
  );
}
