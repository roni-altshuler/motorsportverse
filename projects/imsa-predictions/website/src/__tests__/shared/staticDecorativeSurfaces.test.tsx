import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { MagicCard } from "@/components/magicui/magic-card";
import { Spotlight } from "@/components/magicui/spotlight";
import { NeonGradientCard } from "@/components/magicui/neon-gradient-card";
import { BorderBeam } from "@/components/magicui/border-beam";
import { ShimmerButton } from "@/components/magicui/shimmer-button";
import { PulsatingButton } from "@/components/magicui/pulsating-button";
import { AnimatedGradientText } from "@/components/magicui/animated-gradient-text";
import { Marquee } from "@/components/magicui/marquee";

it("keeps pointer and keyboard controls without scheduling background paint", () => {
  const raf = jest.spyOn(window, "requestAnimationFrame");
  const choose = jest.fn();
  const { container } = render(
    <MagicCard>
      <Spotlight>
        <button onClick={choose}>Choose race</button>
      </Spotlight>
    </MagicCard>,
  );
  fireEvent.mouseMove(container.firstElementChild!, { clientX: 40, clientY: 20 });
  fireEvent.mouseLeave(container.firstElementChild!);
  screen.getByRole("button", { name: "Choose race" }).focus();
  expect(screen.getByRole("button", { name: "Choose race" })).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: "Choose race" }));
  expect(choose).toHaveBeenCalledTimes(1);
  expect(raf).not.toHaveBeenCalled();
  expect(container.querySelector('[aria-hidden="true"]')).toBeNull();
  raf.mockRestore();
});

it("retains CTA actions and disabled behavior without animated layers or leaked motion props", () => {
  const next = jest.fn();
  const { container } = render(
    <NeonGradientCard>
      <BorderBeam duration={8} />
      <ShimmerButton onClick={next} shimmerDuration="2s">
        Next race
      </ShimmerButton>
      <PulsatingButton disabled duration="1s">
        Unavailable
      </PulsatingButton>
      <AnimatedGradientText speed={3}>Forecast</AnimatedGradientText>
    </NeonGradientCard>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Next race" }));
  expect(next).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("button", { name: "Unavailable" })).toBeDisabled();
  expect(
    container.querySelector('[class*="animate-"], [style*="animation"], canvas, animate'),
  ).toBeNull();
  expect(screen.getByRole("button", { name: "Next race" })).not.toHaveAttribute("shimmerduration");
  expect(screen.getByRole("button", { name: "Unavailable" })).not.toHaveAttribute("duration");
  expect(screen.getByText("Forecast")).not.toHaveAttribute("speed");
});

it("shows a single copy of browsable items with a keyboard focus target", () => {
  render(
    <Marquee repeat={4} pauseOnHover aria-label="Racing teams">
      <span>Ferrari</span>
      <span>McLaren</span>
    </Marquee>,
  );
  expect(screen.getAllByText("Ferrari")).toHaveLength(1);
  expect(screen.getAllByText("McLaren")).toHaveLength(1);
  expect(screen.getByRole("region", { name: "Racing teams" })).toHaveAttribute("tabindex", "0");
});
