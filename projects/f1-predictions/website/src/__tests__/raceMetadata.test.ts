import { generateMetadata } from "@/app/race/[round]/page";

jest.mock("@/components/RaceDetailPage", () => () => null);

describe("race publication metadata", () => {
  it("does not advertise a withheld Singapore forecast in search or sharing metadata", async () => {
    const metadata = await generateMetadata({ params: Promise.resolve({ round: "17" }) });
    expect(metadata.title).toContain("Publication review");
    expect(metadata.description).toContain("withdrawn");
    expect(metadata.description).not.toContain("AI-powered");
    expect(JSON.stringify(metadata.openGraph)).not.toContain("predicted podium");
  });
  it("describes Sepang's absent pre-race forecast explicitly", async () => {
    const metadata = await generateMetadata({ params: Promise.resolve({ round: "16" }) });
    expect(metadata.description).toContain("No genuine forecast was published before this race");
    expect(metadata.title).toContain("Publication review");
  });
  it("keeps the existing prediction metadata for an eligible forecast", async () => {
    const metadata = await generateMetadata({ params: Promise.resolve({ round: "15" }) });
    expect(metadata.title).toContain("Predictions");
    expect(metadata.description).toContain("Predicted podium");
  });
});
