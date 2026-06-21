"use client";

import Image from "next/image";
import { useState } from "react";

interface CircuitSpeedMapProps {
  src: string;
  alt: string;
  onLightbox?: () => void;
  onError?: () => void;
}

/**
 * Hybrid circuit speed map: PNG (FastF1 geometry) base + interactive
 * pan/zoom overlay.  Speed-trap markers / DRS-zone shading are
 * deferred to a follow-up data export.
 */
export default function CircuitSpeedMap({ src, alt, onLightbox, onError }: CircuitSpeedMapProps) {
  const [scale, setScale] = useState(1);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [origin, setOrigin] = useState<{ x: number; y: number } | null>(null);

  return (
    <div
      className="relative rounded-lg overflow-hidden select-none"
      style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
    >
      <div
        className="overflow-hidden cursor-grab active:cursor-grabbing"
        onMouseDown={(e) => {
          setDragging(true);
          setOrigin({ x: e.clientX - pos.x, y: e.clientY - pos.y });
        }}
        onMouseUp={() => setDragging(false)}
        onMouseLeave={() => setDragging(false)}
        onMouseMove={(e) => {
          if (!dragging || !origin) return;
          setPos({ x: e.clientX - origin.x, y: e.clientY - origin.y });
        }}
      >
        <div
          style={{
            transform: `translate(${pos.x}px, ${pos.y}px) scale(${scale})`,
            transformOrigin: "center",
            transition: dragging ? undefined : "transform 0.2s ease",
          }}
        >
          <Image
            src={src}
            alt={alt}
            width={1600}
            height={900}
            className="viz-image w-full h-auto"
            style={{ width: "100%", height: "auto" }}
            onError={() => onError?.()}
            unoptimized
            draggable={false}
          />
        </div>
      </div>
      <div className="absolute top-2 right-2 flex items-center gap-2 bg-[color:var(--surface-elevated)] border border-[color:var(--border)] rounded-md px-1 py-1">
        <button
          type="button"
          aria-label="Zoom out"
          onClick={() => setScale((s) => Math.max(1, s - 0.25))}
          className="w-7 h-7 rounded text-sm font-bold text-[color:var(--text-muted)] hover:text-[color:var(--accent-live)]"
        >
          −
        </button>
        <span className="text-[10px] font-mono text-[color:var(--text-muted)]">{Math.round(scale * 100)}%</span>
        <button
          type="button"
          aria-label="Zoom in"
          onClick={() => setScale((s) => Math.min(3, s + 0.25))}
          className="w-7 h-7 rounded text-sm font-bold text-[color:var(--text-muted)] hover:text-[color:var(--accent-live)]"
        >
          +
        </button>
        <button
          type="button"
          aria-label="Reset"
          onClick={() => {
            setScale(1);
            setPos({ x: 0, y: 0 });
          }}
          className="w-7 h-7 rounded text-[10px] font-bold text-[color:var(--text-muted)] hover:text-[color:var(--accent-live)]"
        >
          ⤺
        </button>
        {onLightbox && (
          <button
            type="button"
            aria-label="Fullscreen"
            onClick={onLightbox}
            className="w-7 h-7 rounded text-sm font-bold text-[color:var(--text-muted)] hover:text-[color:var(--accent-live)]"
          >
            ⛶
          </button>
        )}
      </div>
    </div>
  );
}
