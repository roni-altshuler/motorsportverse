import { Suspense } from "react";
import AccuracyDashboardPage from "@/components/AccuracyDashboardPage";
import CalibrationPanel from "@/components/CalibrationPanel";
import { getCalibrationSummary } from "@/lib/calibration";

export default function Page() {
  const calibrationSummary = getCalibrationSummary();

  return (
    <>
      <Suspense
        fallback={
          <div className="min-h-[60vh] flex items-center justify-center">
            <div
              className="loading-pulse text-lg"
              style={{ color: "var(--text-muted)" }}
            >
              Loading accuracy data...
            </div>
          </div>
        }
      >
        <AccuracyDashboardPage />
      </Suspense>

      <section
        aria-labelledby="calibration-heading"
        className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pb-12"
      >
        <h2
          id="calibration-heading"
          className="section-heading"
          style={{ marginBottom: "1rem" }}
        >
          Probability Calibration
        </h2>
        <CalibrationPanel summary={calibrationSummary} />
      </section>
    </>
  );
}
