"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatEntry } from "@/lib/types";

const SUGGESTIONS = ["Who's leading?", "Safety car?", "What's our plan?", "How's the AI car doing?", "Undercut?", "Tyre deg?"];

export function EngineerChat({ chat, onAsk, disabled }: { chat: ChatEntry[]; onAsk: (q: string) => void; disabled: boolean }) {
  const [text, setText] = useState("");
  const log = useRef<HTMLDivElement>(null);
  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight });
  }, [chat.length]);

  const submit = (q: string) => {
    const v = q.trim();
    if (!v) return;
    onAsk(v);
    setText("");
  };

  return (
    <section className="panel chat" aria-label="Ask the race engineer">
      <header className="panel-head">
        <h2>Race engineer</h2>
        <span className="panel-sub">Answers from live data</span>
      </header>
      <div className="chat-log" ref={log}>
        {chat.length === 0 && <p className="empty">Ask about positions, gaps, tyres, the safety car or the plan.</p>}
        {chat.map((c, i) => (
          <div key={i} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <div className="chat-q">{c.question}</div>
            <div className="chat-a">
              <div className="chat-meta num">Lap {c.lap}</div>
              {c.answer}
            </div>
          </div>
        ))}
      </div>
      <div className="chips">
        {SUGGESTIONS.map((s) => (
          <button key={s} className="chip" onClick={() => submit(s)} disabled={disabled}>
            {s}
          </button>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(text);
        }}
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Gap to the car ahead?"
          aria-label="Question for the engineer"
          disabled={disabled}
        />
        <button className="btn" type="submit" disabled={disabled || !text.trim()}>
          Ask
        </button>
      </form>
    </section>
  );
}
