import type { Metadata } from "next";
import { EB_Garamond, JetBrains_Mono, Saira_Condensed } from "next/font/google";

import Footer from "@/components/Footer";
import LiveContextBand from "@/components/race-weekend/LiveContextBand";
import Navbar from "@/components/Navbar";
import SmoothScrollProvider from "@/components/SmoothScrollProvider";

import "./globals.css";

// The exact RaceIQ F1 type system, so F2 reads as part of one product family:
// display = Saira Condensed (headlines + wordmark), body = EB Garamond (serif),
// labels/buttons/captions = JetBrains Mono. F2 keeps its own electric-blue
// identity (--accent:#1E9BD7) — only the typefaces are shared with F1.
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

export const metadata: Metadata = {
  title: "RaceIQ F2 — Formula 2 predictions",
  description:
    "Qualifying, sprint, feature-race, and championship forecasts for the FIA Formula 2 championship, from a model built for a spec series. A MotorsportVerse project on motorsport-core.",
  openGraph: {
    title: "RaceIQ F2 — Formula 2 predictions",
    description:
      "Sprint, feature-race, and championship forecasts for FIA Formula 2 — a MotorsportVerse project.",
    type: "website",
  },
  twitter: { card: "summary_large_image" },
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
        <SmoothScrollProvider>
          <Navbar />
          <LiveContextBand />
          <main id="main-content" tabIndex={-1} className="flex-1 w-full min-h-[70vh]">
            {children}
          </main>
          <Footer />
        </SmoothScrollProvider>
      </body>
    </html>
  );
}
