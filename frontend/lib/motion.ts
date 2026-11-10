"use client";

import { useEffect, useRef, useState } from "react";

export const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Smoothly animates a number towards `target` (ease-out), so readouts count rather than jump. */
export function useTween(target: number | null, duration = 700): number | null {
  const [value, setValue] = useState<number | null>(target);
  const from = useRef<number | null>(target);
  const raf = useRef<number>(0);

  useEffect(() => {
    if (target == null) {
      setValue(null);
      from.current = null;
      return;
    }
    const start = from.current ?? target;
    if (prefersReducedMotion() || start === target) {
      setValue(target);
      from.current = target;
      return;
    }
    const t0 = performance.now();
    const step = (now: number) => {
      const k = Math.min((now - t0) / duration, 1);
      const eased = 1 - Math.pow(1 - k, 3);
      const v = start + (target - start) * eased;
      from.current = v;
      setValue(v);
      if (k < 1) raf.current = requestAnimationFrame(step);
    };
    cancelAnimationFrame(raf.current);
    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
  }, [target, duration]);

  return value;
}
