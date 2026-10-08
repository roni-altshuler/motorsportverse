import { act, render, screen } from "@testing-library/react";
import { hydrateRoot, type Root } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { useReducedMotion } from "@/lib/useReducedMotion";

function Preference({ seen }: { seen?: boolean[] }) {
  const reduced = useReducedMotion();
  seen?.push(reduced);
  return <p data-testid="preference">{reduced ? "reduced" : "normal"}</p>;
}

const original = window.matchMedia;
afterEach(() => {
  window.matchMedia = original;
});

function media(matches: boolean) {
  const listeners = new Set<() => void>();
  const value = {
    matches,
    addEventListener: (_event: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_event: string, listener: () => void) => listeners.delete(listener),
  };
  window.matchMedia = jest.fn(() => value as unknown as MediaQueryList);
  return {
    value,
    listeners,
    change(matches: boolean) {
      value.matches = matches;
      listeners.forEach((listener) => listener());
    },
  };
}

it("hydrates the server snapshot before honoring a reduced-motion browser", async () => {
  media(true);
  const container = document.createElement("div");
  container.innerHTML = renderToString(<Preference />);
  expect(container.textContent).toBe("normal");
  document.body.append(container);
  const seen: boolean[] = [],
    recoverable = jest.fn();
  let root: Root | undefined;
  try {
    await act(async () => {
      root = hydrateRoot(container, <Preference seen={seen} />, {
        onRecoverableError: recoverable,
      });
    });
    expect(seen[0]).toBe(false);
    expect(container.textContent).toBe("reduced");
    expect(recoverable).not.toHaveBeenCalled();
  } finally {
    act(() => root?.unmount());
    container.remove();
  }
});

it("tracks a changed system preference and releases the listener on unmount", () => {
  const source = media(false),
    view = render(<Preference />);
  expect(screen.getByTestId("preference")).toHaveTextContent("normal");
  act(() => source.change(true));
  expect(screen.getByTestId("preference")).toHaveTextContent("reduced");
  act(() => source.change(false));
  expect(screen.getByTestId("preference")).toHaveTextContent("normal");
  view.unmount();
  expect(source.listeners.size).toBe(0);
});

it("renders when the browser has no media-query API", () => {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: undefined,
  });
  render(<Preference />);
  expect(screen.getByTestId("preference")).toHaveTextContent("normal");
});
