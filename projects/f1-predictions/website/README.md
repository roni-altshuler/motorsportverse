# F1 2026 Predictions Website

Interactive Next.js website for viewing ML-powered Formula 1 2026 season predictions.

## Features

- **Home Page** — Season overview, latest race results, championship leaders
- **Calendar** — All 24 Grand Prix with circuit details, tyre degradation, overtaking ratings
- **Race Detail** — Full classification, podium display, circuit info, model metrics, visualizations with lightbox
- **Standings** — Driver & constructor championships with interactive charts, WDC possibility tracker
- **About** — Model architecture, feature descriptions, tech stack

## Quick Start

```bash
cd website
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Data Pipeline

The website reads static JSON and PNG files from `public/data/` and `public/visualizations/`. To regenerate:

```bash
# From f1_predictions root:
python src/export_website_data.py --round 1 --fastf1 --advanced   # Single round
python src/export_website_data.py --all --fastf1 --advanced        # All rounds
python src/export_website_data.py --metadata                       # Season + standings only
```

### Automated Updates

Use the **Update Race Predictions** GitHub Actions workflow to run the pipeline in CI:

1. Go to **Actions → Update Race Predictions → Run workflow**
2. Enter the round number (or `all`)
3. The workflow generates predictions + visualizations, commits them, and triggers a deploy

This keeps the website up-to-date as the 2026 season progresses — each round's predictions, visualizations, and standings are regenerated and published automatically.

## Tech Stack

- Next.js 16 + TypeScript + Tailwind CSS v4
- Recharts for interactive charts
- Python data pipeline (FastF1 + scikit-learn + XGBoost)

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deployment

This site is deployed to **GitHub Pages** via the GitHub Actions workflow in `.github/workflows/deploy.yml`. On every push to `main`, the site is built as a static export and published automatically.
