import type { Metadata } from "next";
import LapComparison from "@/components/comparison/LapComparison";

export const metadata: Metadata = {
  title: "Monaco 2025 — Archived Lap Comparison",
  description:
    "Compare two drivers’ stored Monaco 2025 race laps sector by sector, with the archive’s limits clearly explained.",
  alternates: { canonical: "/compare/laps" },
};

export default function Page() {
  return <LapComparison />;
}
