"use client";

import React, { useEffect, useState } from "react";

export function PresentationCursor() {
  const [enabled, setEnabled] = useState(true);
  const [pos, setPos] = useState({ x: -100, y: -100 });
  const [isClicking, setIsClicking] = useState(false);
  const [ripples, setRipples] = useState<Array<{ id: number; x: number; y: number }>>([]);

  useEffect(() => {
    // Keyboard toggle shortcut: Alt+C
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.altKey && (e.key === "c" || e.key === "C")) {
        setEnabled((prev) => !prev);
      }
    };

    const handleMouseMove = (e: MouseEvent) => {
      setPos({ x: e.clientX, y: e.clientY });
    };

    const handleMouseDown = (e: MouseEvent) => {
      setIsClicking(true);
      const newRipple = { id: Date.now(), x: e.clientX, y: e.clientY };
      setRipples((prev) => [...prev.slice(-4), newRipple]);
      setTimeout(() => {
        setRipples((prev) => prev.filter((r) => r.id !== newRipple.id));
      }, 500);
    };

    const handleMouseUp = () => {
      setIsClicking(false);
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mousedown", handleMouseDown);
    window.addEventListener("mouseup", handleMouseUp);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mousedown", handleMouseDown);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  if (!enabled) return null;

  return (
    <div className="pointer-events-none fixed inset-0 z-[99999999] overflow-hidden">
      {/* Spotlight halo circle following the cursor */}
      <div
        className="pointer-events-none fixed transition-transform duration-75 ease-out"
        style={{
          left: `${pos.x}px`,
          top: `${pos.y}px`,
          transform: `translate(-50%, -50%) scale(${isClicking ? 0.85 : 1})`,
        }}
      >
        {/* Glow halo */}
        <div
          className="w-10 h-10 rounded-full border-2 border-amber-400 bg-amber-400/25 shadow-[0_0_20px_rgba(251,191,36,0.6)] backdrop-blur-[1px]"
          style={{
            boxShadow: isClicking
              ? "0 0 25px rgba(251, 191, 36, 0.9), inset 0 0 10px rgba(251, 191, 36, 0.5)"
              : "0 0 16px rgba(251, 191, 36, 0.6)",
          }}
        />
        {/* Center dot */}
        <div className="absolute top-1/2 left-1/2 w-1.5 h-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-amber-400" />
      </div>

      {/* Expanding click ripple animations */}
      {ripples.map((ripple) => (
        <div
          key={ripple.id}
          className="pointer-events-none fixed w-12 h-12 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-amber-400 bg-amber-400/30 animate-ping duration-500"
          style={{
            left: `${ripple.x}px`,
            top: `${ripple.y}px`,
          }}
        />
      ))}
    </div>
  );
}
