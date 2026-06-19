"use client";

import dynamic from "next/dynamic";

// ssr:false keeps the canvas out of `next build` / static export.
const CheckeredFlagWave = dynamic(() => import("./CheckeredFlagWave"), {
  ssr: false,
});

export default function CheckeredFlagWaveLoader() {
  return <CheckeredFlagWave />;
}
