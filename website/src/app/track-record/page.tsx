import { asset } from "@/lib/asset";
import { getProjects } from "@/lib/registry";

export const metadata = { title: "Model track records | MotorsportVerse" };
export default function TrackRecordsPage() {
  const projects = getProjects().filter(p => p.website && ["production", "experimental"].includes(p.maturity));
  return <div className="shell py-12"><p className="eyebrow">MotorsportVerse</p><h1 className="text-4xl font-bold my-4">Model track records</h1><p className="max-w-3xl mb-8">See original pre-race winner picks, settled results and accuracy over time for each series. Unverified historical comparisons stay separate. A series with no eligible settled races shows “Not yet scored”.</p><div className="grid sm:grid-cols-2 gap-4">{projects.map(p => <a key={p.slug} href={asset(`/projects/${p.slug.replace(/-predictions$/, "")}/track-record${p.slug === "f1-predictions" ? ".html" : "/"}`)} className="block rounded-xl border border-[var(--line)] p-6"><h2 className="text-xl font-bold">{p.name}</h2><span className="underline inline-block py-3">Open winner track record →</span></a>)}</div></div>;
}
