import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import ThemeProvider from "@/components/ThemeProvider";
import { DEFAULT_SEASON_YEAR } from "@/lib/season";

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
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{const t=localStorage.getItem('f1-theme');if(t)document.documentElement.setAttribute('data-theme',t)}catch(e){}`,
          }}
        />
      </head>
      <body className="min-h-screen w-full flex flex-col antialiased" style={{ background: 'var(--bg)', color: 'var(--text)' }}>
        <ThemeProvider>
          <div className="racing-stripe" />
          <Navbar />
          <main className="flex-1 w-full">{children}</main>
          <Footer />
        </ThemeProvider>
      </body>
    </html>
  );
}
