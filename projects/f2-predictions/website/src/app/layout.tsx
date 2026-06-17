import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Saira_Condensed } from "next/font/google";

import { Footer } from "@/components/Footer";
import { Navbar } from "@/components/Navbar";

import "./globals.css";

// Same three families as the MotorsportVerse ecosystem shell + RaceIQ F1, so F2
// reads as part of one product family (display = Saira Condensed, body = Inter,
// mono = JetBrains Mono).
const saira = Saira_Condensed({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-saira",
  display: "swap",
});
const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-inter",
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
    <html lang="en" className={`${saira.variable} ${inter.variable} ${jetbrains.variable}`}>
      <body>
        <Navbar />
        <main className="min-h-[70vh]">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
