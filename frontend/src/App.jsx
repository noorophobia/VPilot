import { useMemo, useRef, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");

function bookingHint(toolEvents) {
  for (const ev of toolEvents || []) {
    if (ev.tool === "book_appointment" && ev.result?.booked) {
      return `Appointment booked: ${ev.result.customer_name} with ${ev.result.doctor} on ${ev.result.date} at ${ev.result.time}.`;
    }
  }
  return null;
}

export default function App() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hi, I'm VPilot — receptionist for Sunrise Family Clinic. Ask about hours, insurance, or book with Dr. Ahmed, Dr. Lee, or Dr. Santos.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const listRef = useRef(null);

  const chatPayload = useMemo(
    () => messages.filter((m) => m.role === "user" || m.role === "assistant"),
    [messages]
  );

  async function sendMessage(e) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    setError("");
    const next = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setLoading(true);

    try {
      if (!API_BASE) {
        throw new Error("VITE_API_URL is not configured. Set it in frontend/.env.");
      }
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: next }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Chat request failed");
      }
      const hint = bookingHint(data.tool_events);
      const reply = hint ? `${data.reply}\n\n${hint}` : data.reply;
      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
    } catch (err) {
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1>VPilot</h1>
        <p>AI clinic receptionist (text MVP)</p>
      </header>

      <main className="chat" ref={listRef}>
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            <span className="label">{m.role === "user" ? "You" : "VPilot"}</span>
            <p>{m.content}</p>
          </div>
        ))}
        {loading && (
          <div className="bubble assistant loading">
            <span className="label">VPilot</span>
            <p>Thinking…</p>
          </div>
        )}
      </main>

      {error && <div className="error">{error}</div>}

      <form className="composer" onSubmit={sendMessage}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about the clinic or book an appointment…"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          Send
        </button>
        <button type="button" className="mic-placeholder" disabled title="Voice layer (later)">
          🎤
        </button>
      </form>
    </div>
  );
}
