import type { Metadata } from "next";
import CircuitReplayWorkspace from "@/components/ui/CircuitReplayWorkspace";
import EnergySandbox from "@/components/engineering/EnergySandbox";
export const metadata: Metadata = {
  title: "Circuit workspace — Local captures & energy sandbox",
  description:
    "Explore local circuit captures and an original synthetic educational energy-management sandbox.",
  alternates: { canonical: "/circuits" },
};
export default function Page() {
  return (
    <>
      <nav
        aria-label="Workspace sections"
        className="mx-auto flex max-w-7xl flex-wrap gap-6 border-b border-hairline px-4 py-5 font-mono text-xs text-muted sm:px-8"
      >
        <a
          href="#local-capture"
          className="flex min-h-11 items-center py-2 text-ink hover:underline"
        >
          Local captures
        </a>
        <a
          href="#energy-sandbox"
          className="flex min-h-11 items-center py-2 text-ink hover:underline"
        >
          Energy sandbox
        </a>
      </nav>
      {/* Keep this short anchor below the expanded header, clear of its
          existing collapse threshold and browser scroll-anchoring feedback. */}
      <div id="local-capture" className="scroll-mt-40">
        <CircuitReplayWorkspace />
      </div>
      <EnergySandbox />
    </>
  );
}
