"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

/**
 * RaceIQ WRC has no standalone /predictions page — the next-rally forecast lives
 * on the home page and the rally-detail page. To avoid 404-ing any inbound links,
 * /predictions now bounces to the next round's rally detail (or standings if the
 * season is complete).
 */
export default function PredictionsRedirect({ round }: { round: number | null }) {
  const router = useRouter();
  const target = round ? `/race/${round}` : "/standings";

  useEffect(() => {
    router.replace(target);
  }, [router, target]);

  return (
    <div className="mx-auto max-w-3xl px-6 py-24 text-center">
      <p className="eyebrow">Redirecting…</p>
      <h1 className="font-display mt-2 text-3xl font-bold text-[var(--ink)]">
        Next-rally forecast
      </h1>
      <p className="mt-3 text-[var(--ink-muted)]">
        The round forecast now lives on the rally page.
      </p>
      <Link
        href={target}
        className="mt-6 inline-block rounded-full border border-[var(--hairline)] px-5 py-2 text-sm font-medium text-[var(--ink)] transition-colors hover:border-[var(--accent)]"
      >
        Continue →
      </Link>
    </div>
  );
}
