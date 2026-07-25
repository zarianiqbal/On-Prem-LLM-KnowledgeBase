import { useRef, useState } from "react";
import { askStream } from "../api";

export default function Chat({ user }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef(null);

  function scrollToBottom() {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
    });
  }

  async function handleSend(e) {
    e.preventDefault();
    const query = input.trim();
    if (!query || busy) return;

    setInput("");
    setMessages((m) => [...m, { role: "user", text: query }]);
    // Placeholder assistant message we stream into.
    setMessages((m) => [...m, { role: "assistant", text: "", citations: [] }]);
    setBusy(true);
    scrollToBottom();

    try {
      await askStream(query, {
        onCitations: (citations) =>
          setMessages((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { ...copy[copy.length - 1], citations };
            return copy;
          }),
        onToken: (token) => {
          setMessages((m) => {
            const copy = [...m];
            const last = copy[copy.length - 1];
            copy[copy.length - 1] = { ...last, text: last.text + token };
            return copy;
          });
          scrollToBottom();
        },
      });
    } catch (err) {
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = {
          role: "assistant",
          text: `⚠️ ${err.message}. Is Ollama running (ollama serve)?`,
          citations: [],
        };
        return copy;
      });
    } finally {
      setBusy(false);
      scrollToBottom();
    }
  }

  return (
    <div className="chat">
      <div className="messages" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="empty muted">
            Ask a question about your company's documents. Answers are drawn only
            from documents your role ({user.roles.join(", ") || "customer"}) can
            access.
          </div>
        )}
        {messages.map((msg, i) => (
          <Message key={i} msg={msg} />
        ))}
      </div>

      <form className="composer" onSubmit={handleSend}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question…"
          disabled={busy}
        />
        <button className="btn-primary" disabled={busy || !input.trim()}>
          {busy ? "…" : "Send"}
        </button>
      </form>
    </div>
  );
}

function Message({ msg }) {
  const isUser = msg.role === "user";
  return (
    <div className={`msg ${isUser ? "msg-user" : "msg-assistant"}`}>
      <div className="bubble">
        {msg.text || <span className="muted">…</span>}
        {!isUser && msg.citations?.length > 0 && (
          <div className="citations">
            <div className="citations-title">Sources</div>
            {msg.citations.map((c, i) => (
              <div className="citation" key={i}>
                <span className="cite-badge">{i + 1}</span>
                <div>
                  <div className="cite-file">
                    {c.filename} · chunk {c.chunk_index} ·{" "}
                    {(c.score * 100).toFixed(0)}% match
                  </div>
                  <div className="cite-snippet muted">{c.snippet}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
