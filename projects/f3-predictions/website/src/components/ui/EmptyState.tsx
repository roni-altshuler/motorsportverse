/**
 * EmptyState — "there is nothing here" rendered as a fact, not as a blank.
 *
 * "No rounds have been scored yet" is information. A page that renders nothing
 * in that case looks broken and gets reported as broken; a page that renders a
 * zero is worse, because a zero is a claim.
 *
 * Every empty state on these sites says three things: what is absent, why, and
 * what would make it appear. The third is the one usually skipped and the one
 * that stops a reader concluding the site is abandoned.
 */
import * as React from "react";
import { cn } from "./cn";

export function EmptyState({
  title,
  description,
  hint,
  action,
  className,
}: {
  /** What is absent. */
  title: string;
  /** Why it is absent — the honest reason, not an apology. */
  description?: string;
  /** What would make it appear. */
  hint?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      data-testid="empty-state"
      role="status"
      className={cn(
        "flex flex-col items-center justify-center gap-2 border border-dashed border-[color:var(--hairline)] px-6 py-12 text-center",
        className,
      )}
    >
      <p className="title-sm text-[color:var(--ink)]">{title}</p>
      {description ? (
        <p className="body-sm max-w-md text-[color:var(--muted)]">{description}</p>
      ) : null}
      {hint ? (
        <p className="max-w-md text-[11px] text-[color:var(--muted)]">{hint}</p>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
