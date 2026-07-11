import type { Metadata } from "next";
import { EB_Garamond, JetBrains_Mono, Saira_Condensed } from "next/font/google";

import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";

import "./globals.css";

// The RaceIQ family type system, so Prism Cup reads as a sibling of the
// ecosystem's sites: display = Saira Condensed (headlines + wordmark),
// body = EB Garamond (serif), labels/buttons/captions = JetBrains Mono.
// Prism Cup keeps its own violet identity (--accent: #7C4DFF) — only the
// typefaces are shared.
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
  title: "Prism Cup Karting — a fan-made simulated kart racing league",
  description:
    "Twelve original racers, eight fantasy circuits, four cups, and a browser-side race simulator with items, boost pads and rubber-banding. A fan-made fictional league — all characters, items, tracks and results are simulated and original. Not affiliated with any video game company.",
  openGraph: {
    title: "Prism Cup Karting — a fan-made simulated kart racing league",
    description:
      "Twelve original racers, eight fantasy circuits, four cups — every result simulated. A MotorsportVerse fun project.",
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
        <Navbar />
        <main id="main-content" tabIndex={-1} className="flex-1 w-full min-h-[70vh]">
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}
