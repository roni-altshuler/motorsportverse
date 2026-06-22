"use client";

import dynamic from "next/dynamic";

// ssr:false keeps the canvas out of `next build` / static export.
const SpeedField = dynamic(() => import("./SpeedField"), { ssr: false });

export default function SpeedFieldLoader() {
  return <SpeedField />;
}
