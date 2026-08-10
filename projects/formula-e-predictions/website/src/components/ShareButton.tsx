"use client";

/**
 * ShareButton — lightweight share cluster (ported from the RaceIQ F1 flagship).
 *
 * Three affordances, each with one job:
 *   1. Native share  — `navigator.share` (mobile / supported browsers only);
 *                      rendered only after we confirm support client-side.
 *   2. Copy link     — clipboard write with an execCommand fallback + a
 *                      transient "Copied" confirmation.
 *   3. Post on X     — a Tweet web-intent in a new tab.
 *
 * This button only needs to hand over the current page URL (read lazily from
 * `window.location` so it stays correct under static export / base paths).
 * The FE electric-blue accent comes for free — the `--accent-f1-red` token is
 * re-pointed to #1E1AF0 in this site's tokens.css.
 */
import { useCallback, useState, useSyncExternalStore } from "react";

interface ShareButtonProps {
  /** Headline used by the native sheet + tweet text, e.g. the E-Prix name. */
  title: string;
  /** Optional longer share blurb; falls back to a sensible default. */
  text?: string;
  className?: string;
}

const BASE_BTN =
  "inline-flex items-center gap-2 border border-[color:var(--hairline-strong)] " +
  "bg-[color:var(--surface-card)] px-4 py-2.5 transition-colors " +
  "hover:border-[color:var(--accent-f1-red)] focus:outline-none " +
  "focus-visible:border-[color:var(--accent-f1-red)]";

function currentUrl(): string {
  return typeof window !== "undefined" ? window.location.href : "";
}

// Client-only capability read via useSyncExternalStore so the server markup
// (no native share) matches hydration without a setState-in-effect.
const noopSubscribe = () => () => {};
const getShareSnapshot = () =>
  typeof navigator !== "undefined" && typeof navigator.share === "function";
const getShareServerSnapshot = () => false;

export default function ShareButton({ title, text, className }: ShareButtonProps) {
  const [copied, setCopied] = useState(false);
  const canNativeShare = useSyncExternalStore(
    noopSubscribe,
    getShareSnapshot,
    getShareServerSnapshot,
  );

  const shareText = text ?? `${title} — Formula E prediction & win-probability forecast`;

  const copyLink = useCallback(async () => {
    const url = currentUrl();
    if (!url) return;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
      } else {
        const ta = document.createElement("textarea");
        ta.value = url;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked — no-op, the tweet/native paths still work */
    }
  }, []);

  const nativeShare = useCallback(async () => {
    const url = currentUrl();
    if (!url || typeof navigator.share !== "function") {
      void copyLink();
      return;
    }
    try {
      await navigator.share({ title, text: shareText, url });
    } catch {
      /* user dismissed the sheet — ignore */
    }
  }, [copyLink, shareText, title]);

  const tweet = useCallback(() => {
    const url = currentUrl();
    const intent =
      "https://twitter.com/intent/tweet?text=" +
      encodeURIComponent(shareText) +
      "&url=" +
      encodeURIComponent(url);
    window.open(intent, "_blank", "noopener,noreferrer");
  }, [shareText]);

  return (
    <div className={`flex flex-wrap items-center gap-2 ${className ?? ""}`}>
      {canNativeShare && (
        <button type="button" onClick={nativeShare} className={BASE_BTN} aria-label="Share this page">
          <svg
            className="h-3.5 w-3.5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
          >
            <circle cx="18" cy="5" r="3" />
            <circle cx="6" cy="12" r="3" />
            <circle cx="18" cy="19" r="3" />
            <line x1="8.6" y1="13.5" x2="15.4" y2="17.5" />
            <line x1="15.4" y1="6.5" x2="8.6" y2="10.5" />
          </svg>
          <span className="button-label text-[color:var(--ink)]">Share</span>
        </button>
      )}

      <button
        type="button"
        onClick={copyLink}
        className={BASE_BTN}
        aria-label={copied ? "Link copied to clipboard" : "Copy link to this page"}
      >
        {copied ? (
          <svg
            className="h-3.5 w-3.5 text-[color:var(--accent-positive)]"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
          >
            <polyline points="20 6 9 17 4 12" />
          </svg>
        ) : (
          <svg
            className="h-3.5 w-3.5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
          >
            <path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.5 1.5" />
            <path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.5-1.5" />
          </svg>
        )}
        <span className="button-label text-[color:var(--ink)]">
          {copied ? "Copied" : "Copy link"}
        </span>
      </button>

      <button type="button" onClick={tweet} className={BASE_BTN} aria-label="Share on X">
        <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
          <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
        </svg>
        <span className="button-label text-[color:var(--ink)]">X</span>
      </button>
    </div>
  );
}
