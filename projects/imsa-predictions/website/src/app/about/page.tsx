import type { Metadata } from "next";
import Link from "next/link";

import { Card } from "@/components/ui/Card";
import { getCalibrationSummary, getImsaData } from "@/lib/imsaData";

export const metadata: Metadata = {
  title: "About — RaceIQ IMSA",
  description:
    "What RaceIQ IMSA predicts and how to read it — win and podium probabilities, class championships, and honest accuracy for the IMSA WeatherTech SportsCar Championship.",
};

export default function Page() {
  const data = getImsaData();
  const calibration = getCalibrationSummary();

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
      <header className="mb-10">
        <p className="eyebrow mb-2">About</p>
        <h1 className="display-lg">Reading the forecasts</h1>
        <p className="body-md mt-4 text-[color:var(--body)]">
          RaceIQ IMSA forecasts the IMSA WeatherTech SportsCar Championship — a win and podium probability for
          every car, in every class, plus each class&rsquo;s title fight. It is part of
          MotorsportVerse, a family of prediction sites built on one shared engine.
        </p>
      </header>

      <div className="flex flex-col gap-4">
        <Card className="p-6">
          <h2 className="title-md mb-2">Multi-class, always</h2>
          <p className="body-md text-[color:var(--body)]">
            Endurance racing runs several classes on track at the same time — {data.classes
              .map((c) => c.label)
              .join(" and ")}{" "}
            this season — and each is its own championship. Every standings table, forecast, and round
            page is filtered by class using the coloured selector at the top; the colours are the
            classes&rsquo; own.
          </p>
        </Card>

        <Card className="p-6">
          <h2 className="title-md mb-2">The unit is a car</h2>
          <p className="body-md text-[color:var(--body)]">
            An entry is a single car — identified by its number, team and manufacturer, shared by a
            lineup of drivers. Points, wins and podiums accrue to the car. Each car has its own page
            with its season results and round-by-round predicted-vs-actual finishes.
          </p>
        </Card>

        <Card className="p-6">
          <h2 className="title-md mb-2">What the numbers mean</h2>
          <p className="body-md text-[color:var(--body)]">
            A <strong>win probability</strong> is the model&rsquo;s estimate of a car winning its
            class; a <strong>podium probability</strong>, of finishing in the class top three. The{" "}
            <strong>predicted classification</strong> is the single most likely finishing order — the
            probabilities describe the spread around it. <strong>Projected points</strong> show a
            P10–P90 range for the rest of the season.
          </p>
        </Card>

        <Card className="p-6">
          <h2 className="title-md mb-2">Honest scoring</h2>
          <p className="body-md text-[color:var(--body)]">
            After every round each class forecast is graded against the real result and published on
            the{" "}
            <Link href="/accuracy" className="link-bugatti">
              accuracy page
            </Link>{" "}
            — mean position error, podium hits and exact finishes, with nothing left out. Endurance
            fields are large, so landing a car within a few places of its prediction is a strong
            result.
            {calibration?.applied
              ? ` Probabilities are calibrated on ${calibration.trainingRounds} real round${
                  calibration.trainingRounds === 1 ? "" : "s"
                } of results so far, per class.`
              : " Calibration is held back until enough real rounds have accrued."}
          </p>
        </Card>

        <Card className="p-6">
          <h2 className="title-md mb-2">Not affiliated, not advice</h2>
          <p className="body-md text-[color:var(--body)]">
            RaceIQ IMSA is an independent MotorsportVerse project. It is not affiliated with IMSA,
            IMSA WeatherTech, or any team, and its forecasts are model estimates — not betting advice.
          </p>
        </Card>
      </div>
    </div>
  );
}
