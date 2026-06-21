import HomePage from "@/components/HomePage";
import { loadTrustStats } from "@/lib/loadTrustStats";

export default function Page() {
  // Honest credibility numbers read off disk at build time (static export).
  const trustStats = loadTrustStats();
  return <HomePage trustStats={trustStats} />;
}
