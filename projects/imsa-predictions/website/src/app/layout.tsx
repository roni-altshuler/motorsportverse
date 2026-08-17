import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";

import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";
import SmoothScrollProvider from "@/components/SmoothScrollProvider";
import { SeasonProvider } from "@/lib/SeasonProvider";

import "./globals.css";

// The exact RaceIQ F1 type system, so IMSA reads as part of one product family:
// display = Saira Condensed (headlines + wordmark), body = EB Garamond (serif),
// labels/buttons/captions = JetBrains Mono. IMSA keeps its own WeatherTech-red
// brand identity (--accent:#E4002B) — only the typefaces are shared.
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

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";
const MANIFEST_URL = `${BASE_PATH}/manifest.webmanifest`;
const APPLE_TOUCH_ICON = `${BASE_PATH}/icons/apple-touch-icon.png`;
const ICON_192 = `${BASE_PATH}/icons/icon-192.png`;
const ICON_512 = `${BASE_PATH}/icons/icon-512.png`;

export const metadata: Metadata = {
  title: "RaceIQ IMSA — IMSA WeatherTech SportsCar Championship predictions",
  description:
    "Race-by-race and championship forecasts for the IMSA WeatherTech SportsCar Championship — win and podium probabilities for every car in GTP, LMP2, GTD PRO and GTD, plus each class's title fight, updated every round. A MotorsportVerse project on motorsport-core.",
  applicationName: "RaceIQ IMSA",
  manifest: MANIFEST_URL,
  appleWebApp: {
    capable: true,
    title: "RaceIQ IMSA",
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
    title: "RaceIQ IMSA — IMSA WeatherTech SportsCar Championship predictions",
    description:
      "Sports-car race and championship forecasts across GTP, LMP2, GTD PRO and GTD — a MotorsportVerse project.",
    type: "website",
  },
  twitter: { card: "summary_large_image" },
};

// Theme-color + color-scheme for the browser chrome / PWA status bar. The app is
// dark-only; the IMSA-red bar mirrors the manifest theme_color.
export const viewport: Viewport = {
  themeColor: "#E4002B",
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
