import type { Metadata } from "next";

import { Footer } from "@/components/Footer";
import { Navbar } from "@/components/Navbar";

import "./globals.css";

export const metadata: Metadata = {
  title: "RaceIQ F2 — Formula 2 predictions",
  description:
    "Calibrated qualifying, race, and championship forecasts for the FIA Formula 2 championship. A MotorsportVerse project built on motorsport-core.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Navbar />
        <main className="min-h-[70vh]">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
