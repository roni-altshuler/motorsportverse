import type { Metadata } from "next";
import { EB_Garamond, JetBrains_Mono, Saira_Condensed } from "next/font/google";

import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";

import "./globals.css";

// The RaceIQ family type system — display = Saira Condensed, body = EB
// Garamond, labels/buttons/captions = JetBrains Mono — re-accented to Chrome
// Valley's canyon orange. Only the typefaces are shared; everything else in
// this league is invented.
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
  title: "Chrome Valley Racing League — a fan-made simulated racing story",
  description:
    "Twelve original racers, ten invented venues, one simulated season. A fan-made fictional league — all characters, venues and results are simulated and original. Not affiliated with any film studio.",
  openGraph: {
    title: "Chrome Valley Racing League — a fan-made simulated racing story",
    description:
      "Twelve original racers, ten invented venues, one simulated season. A fan-made fictional league.",
    type: "website",
  },
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
