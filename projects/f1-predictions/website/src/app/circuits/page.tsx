import type { Metadata } from "next";
import CircuitReplayWorkspace from "@/components/ui/CircuitReplayWorkspace";
export const metadata: Metadata = {
  title: "Circuit workspace — Local capture explorer",
  description:
    "Explore saved circuit snapshots locally, or try an explicitly fictional demonstration.",
  alternates: { canonical: "/circuits" },
};
export default function Page() {
  return <CircuitReplayWorkspace />;
}
