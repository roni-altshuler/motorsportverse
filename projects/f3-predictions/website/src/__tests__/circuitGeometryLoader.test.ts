import { getCircuit, getCircuits } from "@/lib/f3data";

describe("published F3 map gate", () => {
  it("rejects the real conflicting paths without deleting raw recovery data", () => {
    expect(getCircuit("spielberg")).toBeNull();
    expect(getCircuit("silverstone")).toBeNull();
    expect(getCircuits().spielberg.path).toBe(getCircuits().silverstone.path);
  });
  it("preserves the actual nonconflicting Monaco outline without claiming review", () => {
    expect(getCircuit("monaco")?.path).toBe(getCircuits().monaco.path);
    expect(getCircuit("monaco")?.corners).toHaveLength(19);
  });
  it("suppresses ambiguous Hungaroring markers while retaining its outline", () => {
    expect(getCircuit("hungaroring")?.path).toBe(getCircuits().hungaroring.path);
    expect(getCircuit("hungaroring")?.corners).toHaveLength(12);
    expect(getCircuits().hungaroring.corners).toHaveLength(16);
  });
  it("keeps absent and unknown venues unavailable", () => {
    expect(getCircuit("miami")).toBeNull();
    expect(getCircuit("not-in-calendar")).toBeNull();
    expect(getCircuit(undefined)).toBeNull();
  });
});
