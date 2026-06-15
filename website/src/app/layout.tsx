import type { Metadata } from "next";

import { Footer } from "@/components/Footer";
import { Navbar } from "@/components/Navbar";

import "./globals.css";

export const metadata: Metadata = {
  title: "MotorsportVerse — open-source motorsport AI ecosystem",
  description:
    "A unified ecosystem of open-source motorsport prediction projects, built on shared ML and data infrastructure. Discover F1, F2, and more from one place.",
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
