"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { WS_URL } from "./api";
import type { ChatEntry, Frame, RaceSummary, SessionInfo, Summary } from "./types";

type Status = "connecting" | "live" | "closed" | "error";

export function useRaceSession(id: string) {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [race, setRace] = useState<RaceSummary | null>(null);
  const [frames, setFrames] = useState<Frame[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [chat, setChat] = useState<ChatEntry[]>([]);
  const [status, setStatus] = useState<Status>("connecting");
  const [error, setError] = useState<string | null>(null);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    const socket = new WebSocket(`${WS_URL}/ws/sessions/${id}`);
    ws.current = socket;
    socket.onopen = () => setStatus("live");
    socket.onclose = () => setStatus((s) => (s === "error" ? s : "closed"));
    socket.onerror = () => {
      setStatus("error");
      setError("Lost the connection to the strategy server.");
    };
    socket.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      switch (msg.type) {
        case "init":
          setSession(msg.session);
          setRace(msg.race);
          setFrames(msg.frames);
          setSummary(msg.summary);
          break;
        case "lap":
          setFrames((f) => (f.length && f[f.length - 1].lap >= msg.lap ? f : [...f, msg]));
          break;
        case "finished":
          setSummary(msg.summary);
          setSession((s) => (s ? { ...s, finished: true } : s));
          break;
        case "status":
          setSession(msg.session);
          break;
        case "engineer":
          setChat((c) => [...c, { question: msg.question, answer: msg.answer, lap: msg.lap, source: msg.source }]);
          break;
        case "error":
          setStatus("error");
          setError(msg.message);
          break;
      }
    };
    return () => socket.close();
  }, [id]);

  const send = useCallback((payload: object) => {
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify(payload));
  }, []);

  return {
    session,
    race,
    frames,
    latest: frames.length ? frames[frames.length - 1] : null,
    summary,
    chat,
    status,
    error,
    ask: (question: string) => send({ type: "ask", question }),
    pause: () => send({ type: "pause" }),
    resume: () => send({ type: "resume" }),
    setSpeed: (seconds_per_lap: number) => send({ type: "speed", seconds_per_lap }),
    jump: (lap: number) => send({ type: "jump", lap }),
  };
}
