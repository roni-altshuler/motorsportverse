import { getCircuit, getCircuits } from "@/lib/f3data";

describe("published F3 map gate", () => {
  it("rejects the real conflicting paths without deleting raw recovery data", () => {
    expect(getCircuit("spielberg")).toBeNull();
    expect(getCircuit("silverstone")).toBeNull();
    expect(getCircuits().spielberg.path).toBe(getCircuits().silverstone.path);
  });
  it("keeps unreviewed, absent, and unknown venues unavailable", () => {
    expect(getCircuit("monaco")).toBeNull();
    expect(getCircuit("miami")).toBeNull();
    expect(getCircuit("not-in-calendar")).toBeNull();
    expect(getCircuit(undefined)).toBeNull();
  });
});
