import { Suspense } from "react";
import StandingsPage from "@/components/StandingsPage";

export default function Page() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[60vh] flex items-center justify-center">
          <div className="loading-pulse text-lg" style={{ color: "var(--text-muted)" }}>Loading standings...</div>
        </div>
      }
    >
      <StandingsPage />
    </Suspense>
  );
}
