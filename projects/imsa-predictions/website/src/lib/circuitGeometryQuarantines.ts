// Existing conflicting outlines. These are rejection evidence, never approved maps.
// Both labels are quarantined; this does not decide which venue the path depicts.
export const CIRCUIT_GEOMETRY_QUARANTINES = [
  {
    series: "f1",
    season: 2026,
    venueKeys: ["Austria", "Great Britain"],
    viewBox: "0 0 1000 1000",
    path: "M 623.1 768.5 L 444.4 816.7 L 401.6 808.0 L 155.2 382.9 L 4.1 220.9 L 2.1 195.7 L 150.7 183.3 L 633.9 252.2 L 627.0 303.7 L 558.2 354.6 L 344.4 344.5 L 286.3 371.6 L 286.4 458.8 L 378.3 568.1 L 426.0 559.1 L 550.4 475.8 L 884.2 468.2 L 963.3 499.5 L 1000.0 609.7 L 986.2 657.1 L 623.4 768.4 Z",
  },
  {
    series: "f2",
    season: 2026,
    venueKeys: ["spielberg", "silverstone"],
    viewBox: "0 0 1000 1000",
    path: "M 746.7 735.3 L 443.3 817.0 L 404.3 810.2 L 149.9 374.9 L 0.0 198.3 L 148.6 183.0 L 628.2 247.1 L 636.1 289.2 L 584.2 342.6 L 506.8 364.6 L 323.7 347.3 L 282.9 376.9 L 279.1 438.5 L 334.6 535.2 L 388.9 569.6 L 557.2 474.8 L 880.7 468.1 L 953.4 488.8 L 1000.0 606.9 L 991.4 651.4 L 749.4 734.6 Z",
  },
  {
    series: "f3",
    season: 2026,
    venueKeys: ["spielberg", "silverstone"],
    viewBox: "0 0 1000 1000",
    path: "M 746.7 735.3 L 443.3 817.0 L 404.3 810.2 L 149.9 374.9 L 0.0 198.3 L 148.6 183.0 L 628.2 247.1 L 636.1 289.2 L 584.2 342.6 L 506.8 364.6 L 323.7 347.3 L 282.9 376.9 L 279.1 438.5 L 334.6 535.2 L 388.9 569.6 L 557.2 474.8 L 880.7 468.1 L 953.4 488.8 L 1000.0 606.9 L 991.4 651.4 L 749.4 734.6 Z",
  },
] as const;
