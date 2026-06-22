import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
Config.setConcurrency(null); // auto
// Lighter Chrome args for headless CI / container renders.
Config.setChromiumOpenGlRenderer("angle");
