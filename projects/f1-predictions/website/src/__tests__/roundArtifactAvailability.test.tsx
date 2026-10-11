import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import type { RoundData, SeasonData } from "@/types";
import { fetchRoundData } from "@/lib/data";
import { useRoundArtifact } from "@/lib/useRoundArtifact";
import RoundDataStatus from "@/components/race-detail/RoundDataStatus";

jest.mock("@/lib/data", () => ({ fetchRoundData: jest.fn() }));
const fetchRound = jest.mocked(fetchRoundData);
const read = (path: string) => JSON.parse(readFileSync(`public/data/${path}`, "utf8"));
const season: SeasonData = read("season.json");
const singapore: RoundData = read("rounds/round_17.json");
const sepang: RoundData = read("rounds/round_16.json");

function deferred() {
  let resolve!: (value: RoundData) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<RoundData>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}
beforeEach(() => fetchRound.mockReset());

it("keeps a pending artifact hidden and retains its reviewed hold after resolution", async () => {
  const pending = deferred();
  fetchRound.mockReturnValue(pending.promise);
  const { result } = renderHook(() => useRoundArtifact(17, "/data", season));
  expect(result.current).toEqual({ status: "loading", data: null });
  await act(async () => pending.resolve(singapore));
  expect(result.current.status).toBe("ready");
  expect(result.current.data?.publicationHold).toEqual(singapore.publicationHold);
  expect(fetchRound).toHaveBeenCalledWith(17, "/data", season);
});

it("treats a rejected round request as unavailable, without inferring publication", async () => {
  const pending = deferred();
  fetchRound.mockReturnValue(pending.promise);
  const { result } = renderHook(() => useRoundArtifact(17, "/data", season));
  await act(async () => pending.reject(new Error("HTTP 404")));
  expect(result.current).toEqual({ status: "unavailable", data: null });
});

it("clears an old event immediately and ignores a late response after navigation", async () => {
  const old = deferred(),
    current = deferred();
  fetchRound.mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
  const { result, rerender } = renderHook(({ round }) => useRoundArtifact(round, "/data", season), {
    initialProps: { round: 16 },
  });
  rerender({ round: 17 });
  expect(result.current).toEqual({ status: "loading", data: null });
  await act(async () => current.resolve(singapore));
  await act(async () => old.resolve(sepang));
  expect(result.current.data?.round).toBe(17);
  expect(result.current.data?.publicationHold).toEqual(singapore.publicationHold);
});

it.each(["round", "source", "identity"])(
  "hides an already loaded artifact when %s changes",
  async (change) => {
    fetchRound.mockResolvedValueOnce(sepang).mockImplementationOnce(() => new Promise(() => {}));
    const { result, rerender } = renderHook(
      ({ round, base, context }) => useRoundArtifact(round, base, context),
      {
        initialProps: { round: 16, base: "/data", context: season },
      },
    );
    await waitFor(() => expect(result.current.status).toBe("ready"));
    const changed = JSON.parse(JSON.stringify(season)) as SeasonData;
    if (change === "identity") changed.calendar.find((r) => r.round === 16)!.date = "2026-10-12";
    rerender({
      round: change === "round" ? 17 : 16,
      base: change === "source" ? "/archived/data" : "/data",
      context: changed,
    });
    expect(result.current).toEqual({ status: "loading", data: null });
  },
);

it("does not fetch a forecast without a trusted season/event context", () => {
  const { result } = renderHook(() => useRoundArtifact(17, "/data", null));
  expect(result.current).toEqual({ status: "loading", data: null });
  expect(fetchRound).not.toHaveBeenCalled();
});

it("hides previously loaded data while a renewed request for the same event is pending", async () => {
  fetchRound.mockResolvedValueOnce(singapore).mockImplementationOnce(() => new Promise(() => {}));
  const { result, rerender } = renderHook(({ context }) => useRoundArtifact(17, "/data", context), {
    initialProps: { context: season },
  });
  await waitFor(() => expect(result.current.status).toBe("ready"));
  rerender({ context: JSON.parse(JSON.stringify(season)) });
  expect(result.current).toEqual({ status: "loading", data: null });
});

it.each(["loading", "unavailable"] as const)(
  "describes %s inputs without an unpublished or automatic-publication claim",
  (status) => {
    render(<RoundDataStatus status={status} />);
    expect(
      screen.getByRole("heading", { name: "Forecast status cannot currently be verified" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(
        /not published predictions|automatically appear|workflow runs|forecast will appear/i,
      ),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/Forecasts and the grid baseline stay hidden/)).toBeInTheDocument();
  },
);
