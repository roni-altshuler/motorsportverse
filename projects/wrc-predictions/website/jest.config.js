// Jest, wired through next/jest so the project's own SWC transform, path
// aliases and CSS handling apply — hand-rolling a babel transform here is how a
// test suite ends up compiling differently from the site it tests.
const nextJest = require("next/jest");

const createJestConfig = nextJest({ dir: "./" });

module.exports = createJestConfig({
  testEnvironment: "jest-environment-jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.js"],
  moduleNameMapper: { "^@/(.*)$": "<rootDir>/src/$1" },
  testPathIgnorePatterns: ["<rootDir>/node_modules/", "<rootDir>/.next/", "<rootDir>/out/"],
});
