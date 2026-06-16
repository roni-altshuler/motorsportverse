import type { Metadata } from "next";

import { Footer } from "@/components/Footer";
import { Navbar } from "@/components/Navbar";

import "./globals.css";

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
    <html lang="en">
      <body>
        <Navbar />
        <main className="min-h-[70vh]">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
