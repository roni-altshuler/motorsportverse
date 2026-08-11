import { Badge } from "@/components/ui/Badge";

/** Maps the export's confidence string to a Badge tone. Purely descriptive of
 *  how sure the forecast is — never names a method. */
export default function ConfidenceBadge({ confidence }: { confidence: string }) {
  const c = confidence.toLowerCase();
  const variant = c === "high" ? "positive" : c === "medium" ? "info" : "muted";
  return <Badge variant={variant}>{confidence}</Badge>;
}
