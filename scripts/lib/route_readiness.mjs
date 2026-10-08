import assert from "node:assert/strict";

// A matching URL and layout landmark do not prove that an App Router
// destination has committed. Require its own content and rendered identity.
export async function waitForRouteReady(page, expected, timeout = 15000) {
  assert.ok(
    expected.path && expected.headings?.length,
    "A route needs an explicit path and heading identity",
  );
  await page.evaluate(() => {
    window.__qaRouteStable = null;
  });
  try {
    // Titles below long evidence sections reveal on entering the viewport.
    // Scroll the real destination identity into view before testing its paint.
    const heading = await page.waitForFunction(
      (expected) => {
        if (
          location.pathname.replace(/\/$/, "") !==
          expected.path.replace(/\/$/, "")
        )
          return false;
        const { level, text } = expected.headings[0];
        return (
          [...document.querySelectorAll(`main h${level}`)].find((el) => {
            const copy = el.cloneNode(true);
            copy
              .querySelectorAll('img, svg, [role="img"], [aria-hidden="true"]')
              .forEach((image) => image.remove());
            return (
              copy.textContent.replace(/\s+/g, " ").trim() ===
              text.replace(/\s+/g, " ").trim()
            );
          }) || false
        );
      },
      expected,
      { timeout, polling: "raf" },
    );
    try {
      await heading.evaluate((el) =>
        el.scrollIntoView({ behavior: "instant", block: "center" }),
      );
    } finally {
      await heading.dispose();
    }
    const result = await page.waitForFunction(
      (expected) => {
        const reject = () => {
          window.__qaRouteStable = null;
          return false;
        };
        const normal = (text) => text.replace(/\s+/g, " ").trim();
        const headingText = (el) => {
          const copy = el.cloneNode(true);
          copy
            .querySelectorAll('img, svg, [role="img"], [aria-hidden="true"]')
            .forEach((image) => image.remove());
          return normal(copy.textContent);
        };
        const visible = (el) =>
          el.getClientRects().length &&
          getComputedStyle(el).visibility !== "hidden";
        const main = document.querySelector("main");
        if (
          !main ||
          location.pathname.replace(/\/$/, "") !==
            expected.path.replace(/\/$/, "")
        )
          return reject();
        const matches = expected.headings.map(({ level, text }) =>
          [...main.querySelectorAll(`h${level}`)].find(
            (el) => headingText(el) === normal(text),
          ),
        );
        if (matches.some((el) => !el)) return reject();
        if (
          !(expected.text ?? []).every((text) =>
            normal(main.textContent).includes(normal(text)),
          )
        )
          return reject();
        if (
          !(expected.selectors ?? []).every((selector) =>
            main.querySelector(selector),
          )
        )
          return reject();
        const primary = matches[0];
        if (!visible(primary)) return reject();
        const primaryStyles = [];
        let primaryOpacity = 1;
        for (let el = primary; el && el !== main; el = el.parentElement) {
          const style = getComputedStyle(el);
          primaryOpacity *= Number(style.opacity);
          primaryStyles.push([
            style.opacity,
            style.transform,
            style.visibility,
          ]);
          if (style.visibility === "hidden") return reject();
        }
        if (primaryOpacity < 0.999) return reject();
        const pendingLocalFetches = window.__qaPendingFetch ?? 0;
        const loadingIndicators = [
          ...main.querySelectorAll('.loading-pulse, [aria-busy="true"]'),
        ].filter(visible).length;
        if (
          !expected.loadingFixture &&
          (pendingLocalFetches !== 0 || loadingIndicators !== 0)
        )
          return reject();
        if (document.fonts.status !== "loaded") return reject();
        const rect = primary.getBoundingClientRect();
        const primaryGeometry = {
          x: rect.x,
          y: rect.y,
          width: rect.width,
          height: rect.height,
        };
        // Settle the destination identity and page width, not live/animated
        // chart values elsewhere on the page. Loading and identity are checked
        // again on every frame and reset the consecutive count when incomplete.
        const value = JSON.stringify([
          matches.map(headingText),
          document.documentElement.scrollWidth,
          primaryStyles,
        ]);
        const previous = window.__qaRouteStable;
        const geometrySettled =
          previous &&
          Object.keys(primaryGeometry).every(
            (key) =>
              Math.abs(primaryGeometry[key] - previous.geometry[key]) <= 0.5,
          );
        const settled = previous?.value === value && geometrySettled;
        window.__qaRouteStable = {
          value,
          geometry: settled ? previous.geometry : primaryGeometry,
          frames: settled ? previous.frames + 1 : 0,
        };
        if (window.__qaRouteStable.frames < 3) return false;
        return {
          expected,
          observedHeadings: [...main.querySelectorAll("h1, h2, h3")].map(
            (el) => ({
              level: Number(el.tagName[1]),
              text: normal(el.textContent),
              identityText: headingText(el),
            }),
          ),
          pendingLocalFetches,
          loadingIndicators,
          primaryHeadingOpacity: primaryOpacity,
          primaryHeadingGeometry: primaryGeometry,
          geometryTolerancePx: 0.5,
          stableRenderedFrames: window.__qaRouteStable.frames,
          fontsStatus: document.fonts.status,
        };
      },
      expected,
      { timeout, polling: "raf" },
    );
    try {
      return await result.jsonValue();
    } finally {
      await result.dispose();
    }
  } catch (error) {
    const observed = await page.evaluate(() => ({
      path: location.pathname,
      headings: [...document.querySelectorAll("main h1, main h2, main h3")].map(
        (el) => el.textContent.replace(/\s+/g, " ").trim(),
      ),
      pendingFetches: window.__qaPendingFetch ?? 0,
      fontsStatus: document.fonts.status,
      stableFrames: window.__qaRouteStable?.frames ?? null,
      headingStyles: [...document.querySelectorAll("main h1")].map((el) => {
        const styles = [];
        for (
          let node = el;
          node && node.tagName !== "MAIN";
          node = node.parentElement
        ) {
          const style = getComputedStyle(node);
          styles.push({
            tag: node.tagName,
            opacity: style.opacity,
            transform: style.transform,
            visibility: style.visibility,
          });
        }
        return {
          text: el.textContent,
          y: el.getBoundingClientRect().y,
          styles,
        };
      }),
      loading: [...document.querySelectorAll("main .loading-pulse")].map(
        (el) => el.textContent,
      ),
      mainText: document
        .querySelector("main")
        ?.textContent.replace(/\s+/g, " ")
        .trim()
        .slice(0, 600),
    }));
    throw new Error(
      error.message +
        "; route readiness " +
        JSON.stringify({ expected, observed }),
      { cause: error },
    );
  }
}
