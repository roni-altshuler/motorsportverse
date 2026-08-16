require("@testing-library/jest-dom");

// jsdom implements neither of these, and both are used by the shared motion
// primitives. Without the stubs every component that reveals on scroll throws
// on mount, which reads as "the component is broken" rather than "the test
// environment is incomplete".
global.IntersectionObserver = class {
  constructor(callback) {
    this.callback = callback;
  }
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
};

if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener() {},
    removeListener() {},
    addEventListener() {},
    removeEventListener() {},
    dispatchEvent() {
      return false;
    },
  });
}
