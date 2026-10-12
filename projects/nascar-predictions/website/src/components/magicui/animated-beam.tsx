"use client";

import { forwardRef, useEffect, useId, useState, type RefObject } from "react";

import { cn } from "@/components/ui/cn";

export interface AnimatedBeamProps {
  className?: string;
  containerRef: RefObject<HTMLElement | null>;
  fromRef: RefObject<HTMLElement | null>;
  toRef: RefObject<HTMLElement | null>;
  curvature?: number;
  reverse?: boolean;
  pathColor?: string;
  pathWidth?: number;
  pathOpacity?: number;
  gradientStartColor?: string;
  gradientStopColor?: string;
  delay?: number;
  duration?: number;
  startXOffset?: number;
  startYOffset?: number;
  endXOffset?: number;
  endYOffset?: number;
}

/**
 * Static SVG connector between two refs.  Compute the bounding boxes
 * of `fromRef` and `toRef` relative to `containerRef`, draw a curved path,
 * and stroke a fixed gradient along the path.
 *
 * For the F1 about-page diagram: Live Data → AI Model → Forecast.
 */
export const AnimatedBeam = forwardRef<SVGSVGElement, AnimatedBeamProps>(function AnimatedBeam(
  {
    className,
    containerRef,
    fromRef,
    toRef,
    curvature = 0,
    reverse = false,
    pathColor = "rgba(255,255,255,0.10)",
    pathWidth = 2,
    pathOpacity = 1,
    gradientStartColor = "#E10600",
    gradientStopColor = "#FFD166",
    startXOffset = 0,
    startYOffset = 0,
    endXOffset = 0,
    endYOffset = 0,
  },
  ref,
) {
  const id = useId();
  const [geometry, setGeometry] = useState({
    path: "",
    width: 0,
    height: 0,
    startX: 0,
    startY: 0,
    endX: 0,
    endY: 0,
  });

  useEffect(() => {
    const updatePath = () => {
      if (!containerRef.current || !fromRef.current || !toRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const rectA = fromRef.current.getBoundingClientRect();
      const rectB = toRef.current.getBoundingClientRect();
      const svgWidth = containerRect.width;
      const svgHeight = containerRect.height;

      const startX = rectA.left - containerRect.left + rectA.width / 2 + startXOffset;
      const startY = rectA.top - containerRect.top + rectA.height / 2 + startYOffset;
      const endX = rectB.left - containerRect.left + rectB.width / 2 + endXOffset;
      const endY = rectB.top - containerRect.top + rectB.height / 2 + endYOffset;

      const controlY = startY - curvature;
      const d = `M ${startX},${startY} Q ${(startX + endX) / 2},${controlY} ${endX},${endY}`;
      setGeometry({ path: d, width: svgWidth, height: svgHeight, startX, startY, endX, endY });
    };

    const ro = new ResizeObserver(updatePath);
    if (containerRef.current) ro.observe(containerRef.current);
    updatePath();
    return () => ro.disconnect();
  }, [containerRef, fromRef, toRef, curvature, startXOffset, startYOffset, endXOffset, endYOffset]);

  return (
    <svg
      ref={ref}
      width={geometry.width}
      height={geometry.height}
      xmlns="http://www.w3.org/2000/svg"
      className={cn("pointer-events-none absolute left-0 top-0 transform-gpu stroke-2", className)}
      viewBox={`0 0 ${geometry.width} ${geometry.height}`}
      aria-hidden
    >
      <path
        d={geometry.path}
        stroke={pathColor}
        strokeWidth={pathWidth}
        strokeOpacity={pathOpacity}
        strokeLinecap="round"
      />
      <path
        d={geometry.path}
        strokeWidth={pathWidth}
        stroke={`url(#${id})`}
        strokeOpacity="1"
        strokeLinecap="round"
      />
      <defs>
        <linearGradient
          id={id}
          gradientUnits="userSpaceOnUse"
          x1={reverse ? geometry.endX : geometry.startX}
          y1={reverse ? geometry.endY : geometry.startY}
          x2={reverse ? geometry.startX : geometry.endX}
          y2={reverse ? geometry.startY : geometry.endY}
        >
          <stop stopColor={gradientStartColor} />
          <stop offset="100%" stopColor={gradientStopColor} />
        </linearGradient>
      </defs>
    </svg>
  );
});
