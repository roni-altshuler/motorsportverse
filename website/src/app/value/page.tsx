import type { Metadata } from "next";
import { Suspense } from "react";
import ValueFinder from "@/components/ValueFinder";

export const dynamic = "force-static";

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";
const OG_DEFAULT = `${BASE_PATH}/og/default.png`;

const title = "Value Finder — F1 Predictions";
const description =
  "Pre-race betting edges: model probabilities vs sportsbook odds, with fractional Kelly sizing. Educational use only.";

export const metadata: Metadata = {
  title,
  description,
  openGraph: {
    type: "website",
    title,
    description,
    url: "/value",
    images: [
      {
        url: OG_DEFAULT,
        width: 1200,
        height: 630,
        alt: "F1 Predictions — Value Finder",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: [OG_DEFAULT],
  },
};

export default function Page() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[60vh] flex items-center justify-center">
          <div
            className="loading-pulse text-lg"
            style={{ color: "var(--text-muted)" }}
          >
            Loading value finder...
          </div>
        </div>
      }
    >
      <ValueFinder />
    </Suspense>
  );
}
