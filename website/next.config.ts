import type { NextConfig } from "next";
import { resolve } from "node:path";

const basePath = process.env.PAGES_BASE_PATH || "";

const nextConfig: NextConfig = {
  output: "export",
  // Keep bundling inside this monorepo even when a parent workspace has a lockfile.
  turbopack: { root: resolve(__dirname, "..") },
  trailingSlash: true,
  basePath,
  env: { NEXT_PUBLIC_BASE_PATH: basePath },
  images: { unoptimized: true },
};

export default nextConfig;
