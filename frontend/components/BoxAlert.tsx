"use client";

import { useEffect, useRef, useState } from "react";
import type { Call, Frame } from "@/lib/types";

/** Full-width "BOX BOX" sweep across the track map whenever the AI calls a stop. */
export function BoxAlert({ frame }: { frame: Frame }) {
  const [call, setCall] = useState<Call | null>(null);
  const seen = useRef<number>(-1);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    if (frame.lap === seen.current) return;
    seen.current = frame.lap;
    const box = frame.calls.find((c) => c.kind === "BOX" || c.kind === "SC_BOX");
    if (!box) return;
    setCall(box);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setCall(null), 2600);
  }, [frame]);

  useEffect(() => () => clearTimeout(timer.current), []);
  if (!call) return null;
  return (
    <div className="box-alert" role="alert" key={`${call.lap}-${call.kind}`}>
      <div className="box-alert-band">
        <span className="box-alert-word">BOX BOX</span>
        <span className="box-alert-msg">{call.message.replace(/^BOX BOX\.\s*/, "")}</span>
      </div>
    </div>
  );
}
