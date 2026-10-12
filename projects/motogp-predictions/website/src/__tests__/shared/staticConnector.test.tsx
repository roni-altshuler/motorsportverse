import "@testing-library/jest-dom";
import { render } from "@testing-library/react";
import { AnimatedBeam } from "@/components/magicui/animated-beam";

const originalResizeObserver = global.ResizeObserver;
beforeEach(() => {
  global.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as typeof ResizeObserver;
});
afterEach(() => {
  global.ResizeObserver = originalResizeObserver;
});

function element(left: number, top: number, width: number, height: number) {
  const node = document.createElement("div");
  node.getBoundingClientRect = () => ({
    left,
    top,
    width,
    height,
    right: left + width,
    bottom: top + height,
    x: left,
    y: top,
    toJSON: () => ({}),
  });
  return { current: node };
}

it.each(["horizontal", "vertical"] as const)(
  "keeps a colored static %s connector with a degenerate path bounding box",
  (direction) => {
    const containerRef = element(10, 20, 400, 300);
    const fromRef = element(50, 100, 20, 20);
    const toRef = direction === "horizontal" ? element(250, 100, 20, 20) : element(50, 220, 20, 20);
    const { container } = render(
      <AnimatedBeam containerRef={containerRef} fromRef={fromRef} toRef={toRef} />,
    );
    const gradient = container.querySelector("linearGradient")!;
    expect(gradient).toHaveAttribute("gradientUnits", "userSpaceOnUse");
    expect(gradient).toHaveAttribute("x1", "50");
    expect(gradient).toHaveAttribute("y1", "90");
    expect(gradient).toHaveAttribute("x2", direction === "horizontal" ? "250" : "50");
    expect(gradient).toHaveAttribute("y2", direction === "horizontal" ? "90" : "210");
    expect(container.querySelector('path[stroke^="url"]')).toHaveAttribute(
      "d",
      expect.stringContaining("M 50,90"),
    );
    expect(container.querySelector("animate, animateTransform")).toBeNull();
  },
);
