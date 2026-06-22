import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Saira_Condensed } from "next/font/google";

import SpeedFieldLoader from "@/components/background/SpeedFieldLoader";
import { CommandPaletteProvider } from "@/components/CommandPaletteProvider";
import { Footer } from "@/components/Footer";
import { Navbar } from "@/components/Navbar";

import "./globals.css";

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
  metadataBase: new URL("https://roni-altshuler.github.io/motorsportverse/"),
  title: "MotorsportVerse — open-source motorsport AI ecosystem",
  description:
    "A unified ecosystem of open-source motorsport prediction projects, built on shared ML and data infrastructure. Discover F1, F2, and more from one place.",
  openGraph: {
    title: "MotorsportVerse — open-source motorsport AI ecosystem",
    description:
      "A unified ecosystem of open-source motorsport prediction projects on shared ML & data infrastructure.",
    images: ["brand/motorsportverse-logo.png"],
    type: "website",
  },
  twitter: { card: "summary_large_image", images: ["brand/motorsportverse-logo.png"] },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${saira.variable} ${inter.variable} ${jetbrains.variable}`}>
      <body>
        {/* Site-wide cinematic light-trail background (fixed, z-0). Content
            below is lifted above it so the streaks show through behind it. */}
        <SpeedFieldLoader />
        <Navbar />
        <main className="relative z-[1] min-h-[70vh]">{children}</main>
        <Footer />
        <CommandPaletteProvider />
      </body>
    </html>
  );
}
