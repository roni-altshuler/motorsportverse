# MotorsportVerse — product film (Remotion)

Renders the "how the prediction engine works" walkthrough to an MP4 that the
website plays in the **ProductFilm** section.

```bash
cd remotion
npm install
npm run studio     # live-edit the composition at localhost:3000
npm run release    # render → web-optimize (ffmpeg) → sync into ../website/public/film/
```

`release` runs: `render` (h264) → `still` (poster) → `web` (faststart/yuv420p, audio
stripped) → `sync` (copies `motorsportverse-engine.mp4` + `engine-poster.png` into
`website/public/film/`). The website build does **not** depend on this workspace —
it only consumes the committed MP4 + poster.

Composition source: `src/Film.tsx` (scenes) + `src/Root.tsx` (registration).
