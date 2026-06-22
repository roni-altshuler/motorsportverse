import { Composition } from "remotion";

import { Film, FILM_DURATION, FPS, HEIGHT, WIDTH } from "./Film";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="MotorsportVerseFilm"
      component={Film}
      durationInFrames={FILM_DURATION}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
  );
};
