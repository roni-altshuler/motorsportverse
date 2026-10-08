"use client";

import type { ReactNode } from "react";

/** Resolve a pending route on a component fiber, rather than replaying <main>
 * against its own already-entered hydration contents. This emits no wrapper. */
function RouteContent({ children }: { children: ReactNode }) {
  return children;
}

export default function RouteMain({ children }: { children: ReactNode }) {
  return (
    <main id="main-content" tabIndex={-1} className="flex-1 w-full">
      <RouteContent>{children}</RouteContent>
    </main>
  );
}
