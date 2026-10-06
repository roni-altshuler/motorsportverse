import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import CircuitMapUnavailable from "@/components/ui/CircuitMapUnavailable";

describe("map absence", () => {
  it("names the venue without inventing an outline or explorer controls", () => {
    const { container } = render(<CircuitMapUnavailable venue="Silverstone" />);
    expect(screen.getByRole("status", { name: "Circuit map availability" })).toHaveTextContent(
      "A circuit layout is not available for Silverstone.",
    );
    expect(container.querySelector("svg, img, button, a")).toBeNull();
  });
  it("does not substitute an invented venue when identity is absent", () => {
    render(<CircuitMapUnavailable />);
    expect(
      screen.getByText("A circuit layout is not available for this event."),
    ).toBeInTheDocument();
  });
});
