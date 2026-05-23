import type { Metadata } from "next";
import { Saira_Condensed, EB_Garamond, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import LiveContextBand from "@/components/race-weekend/LiveContextBand";
import SmoothScrollProvider from "@/components/SmoothScrollProvider";
import { DEFAULT_SEASON_YEAR } from "@/lib/season";

// Bugatti redesign uses the recommended open-source substitutes for the three
// licensed Bugatti typefaces: Saira Condensed (display headlines + wordmark),
// EB Garamond (serif body), JetBrains Mono (buttons + nav + captions). All at
// weight 400 — Bugatti's system has no bold role.
const sairaCondensed = Saira_Condensed({
  subsets: ["latin"],
  variable: "--font-saira-condensed",
  weight: "400",
  display: "swap",
});

const ebGaramond = EB_Garamond({
  subsets: ["latin"],
  variable: "--font-eb-garamond",
  weight: "400",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  weight: "400",
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

const SITE_TITLE = `F1 ${ACTIVE_SEASON_YEAR} Predictions | AI-Powered Race Forecasts`;
const SITE_DESCRIPTION =
  `AI and machine learning-powered Formula 1 ${ACTIVE_SEASON_YEAR} season predictions. ` +
  "Race classifications, championship standings, pit strategy simulations, " +
  "and professional visualizations for every Grand Prix.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: SITE_TITLE,
  description: SITE_DESCRIPTION,
  openGraph: {
    type: "website",
    siteName: "F1 Predictions",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    url: "/",
    images: [
      {
        url: OG_DEFAULT,
        width: 1200,
        height: 630,
        alt: `F1 ${ACTIVE_SEASON_YEAR} Predictions — AI-powered race forecasts`,
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
        <SmoothScrollProvider>
          <Navbar />
          <LiveContextBand />
          <main id="main-content" tabIndex={-1} className="flex-1 w-full">{children}</main>
          <Footer />
        </SmoothScrollProvider>
      </body>
    </html>
  );
}
