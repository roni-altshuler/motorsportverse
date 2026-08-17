import type { Metadata } from "next";
import localFont from "next/font/local";

import SpeedFieldLoader from "@/components/background/SpeedFieldLoader";
import { CommandPaletteProvider } from "@/components/CommandPaletteProvider";
import { Footer } from "@/components/Footer";
import { Navbar } from "@/components/Navbar";

import "./globals.css";

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
const inter = localFont({
  src: [
    { path: "./fonts/Inter-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/Inter-500.woff2", weight: "500", style: "normal" },
    { path: "./fonts/Inter-600.woff2", weight: "600", style: "normal" },
  ],
  variable: "--font-inter",
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
