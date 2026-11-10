"use client";

import { useEffect, useLayoutEffect, useState } from "react";
import { ParallaxMark } from "./Logo";

const KEY = "parallax-intro-seen";
const DURATION = 2600;
const useIsoLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;

/** Opening title card, shown once per browser session. Any key or click skips it. */
export function Intro() {
  const [phase, setPhase] = useState<"show" | "leaving" | "gone">("show");

  useIsoLayoutEffect(() => {
    let seen = false;
    try {
      seen = sessionStorage.getItem(KEY) === "1";
      sessionStorage.setItem(KEY, "1");
    } catch {
      /* storage blocked: just play the intro */
    }
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (seen) {
      setPhase("gone");
      return;
    }
    const leave = setTimeout(() => setPhase("leaving"), reduced ? 900 : DURATION);
    const done = setTimeout(() => setPhase("gone"), (reduced ? 900 : DURATION) + 450);
    const skip = () => {
      setPhase("leaving");
      setTimeout(() => setPhase("gone"), 450);
    };
    window.addEventListener("keydown", skip, { once: true });
    return () => {
      clearTimeout(leave);
      clearTimeout(done);
      window.removeEventListener("keydown", skip);
    };
  }, []);

  if (phase === "gone") return null;
  return (
    <div
      className={`intro${phase === "leaving" ? " intro--leaving" : ""}`}
      onClick={() => {
        setPhase("leaving");
        setTimeout(() => setPhase("gone"), 450);
      }}
      aria-hidden
    >
      <div className="intro-inner">
        <ParallaxMark size={96} motion="intro" />
        <div className="intro-word">PARALLAX</div>
        <div className="intro-tag">The race that could have been.</div>
      </div>
    </div>
  );
}
