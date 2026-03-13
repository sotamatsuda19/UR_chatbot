const { useState, useEffect, useRef } = React;

const EMPTY_PROMPTS = [
  "What would you like to know about UR?",
  "Ask me anything about UR.",
  "Curious about student life? Ask away.",
  "Got a question about UR? I'm here.",
  "What can I help you with today?",
  "Wondering about majors or research? Just ask.",
  "Ask me anything — academics, housing, dining.",
  "Not sure where to start? Just ask.",
  "Looking for info about UR? I've got you.",
  "Academics or campus life — ask away.",
];

const randomPrompt = EMPTY_PROMPTS[Math.floor(Math.random() * EMPTY_PROMPTS.length)];

function Chatbot() {
  const [messages, setMessages] = useState([]);
  const [input, setInput]       = useState("");
  const [loading, setLoading]   = useState(false);
  const bottomRef               = useRef(null);
  const isEmpty                 = messages.length === 0;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const question = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setLoading(true);

    try {
      const history = messages.map((m) => ({
        role:    m.role === "user" ? "user" : "assistant",
        content: m.text,
      }));

      const res  = await fetch(`${window.__API_BASE__}/chat`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ question, history }),
      });
      const data = await res.json();
      setMessages((prev) => [...prev, { role: "assistant", text: data.answer }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", text: "Something went wrong. Please try again." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen flex flex-col">

      {/* Header — top-left corner */}
      <div className="absolute top-6 left-8">
        <div className="flex items-center gap-3">
          <img src="./logo.png" alt="University of Rochester" className="h-10" />
          <span className="text-slate-300 text-xl font-light">|</span>
          <span className="text-slate-600 text-sm font-medium tracking-wide uppercase">Chatbot</span>
        </div>
        <p className="text-slate-400 text-sm mt-2">Your AI guide to the University of Rochester</p>
      </div>

      {/* Chat area */}
      <div className="flex flex-col flex-1 w-full max-w-2xl mx-auto px-4">

        {isEmpty ? (
          /* ── Empty state: input centered vertically ── */
          <div className="flex flex-col justify-center flex-1 gap-8">
            <p className="text-center text-slate-600 text-xl font-medium">{randomPrompt}</p>
            <form onSubmit={handleSubmit} className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about the University of Rochester..."
                disabled={loading}
                className="flex-1 bg-slate-100 rounded-xl px-5 py-4 text-base text-slate-800 placeholder-slate-400 outline-none focus:ring-2 focus:ring-blue-300"
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="bg-blue-700 hover:bg-blue-800 disabled:opacity-40 text-white px-5 py-4 rounded-xl transition-colors flex items-center justify-center"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                  <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
                </svg>
              </button>
            </form>
          </div>
        ) : (
          /* ── Chat state: messages + input at bottom ── */
          <>
            <div className="flex-1 overflow-y-auto pt-32 pb-4 space-y-4">
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`fade-up flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`message-bubble px-4 py-3 rounded-2xl text-sm ${
                      msg.role === "user"
                        ? "bg-blue-700 text-white rounded-br-sm"
                        : "bg-slate-100 text-slate-800 rounded-bl-sm"
                    }`}
                  >
                    {msg.text}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="fade-up flex justify-start">
                  <div className="message-bubble bg-slate-100 px-4 py-3 rounded-2xl rounded-bl-sm flex gap-1 items-center">
                    <span className="dot w-2 h-2 bg-slate-400 rounded-full inline-block"></span>
                    <span className="dot w-2 h-2 bg-slate-400 rounded-full inline-block"></span>
                    <span className="dot w-2 h-2 bg-slate-400 rounded-full inline-block"></span>
                  </div>
                </div>
              )}

              <div ref={bottomRef} />
            </div>

            <form onSubmit={handleSubmit} className="py-3 flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about the University of Rochester..."
                disabled={loading}
                className="flex-1 bg-slate-100 rounded-xl px-4 py-3 text-sm text-slate-800 placeholder-slate-400 outline-none focus:ring-2 focus:ring-blue-300 disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="bg-blue-700 hover:bg-blue-800 disabled:opacity-40 text-white px-4 py-3 rounded-xl transition-colors flex items-center justify-center"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                  <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
                </svg>
              </button>
            </form>

            <p className="text-xs text-slate-400 text-center pb-2">
              This chatbot can make mistakes. Verify important information with official UR sources.
            </p>
          </>
        )}

      </div>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<Chatbot />);
