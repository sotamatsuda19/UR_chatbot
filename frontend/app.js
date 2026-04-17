const { useState, useEffect, useRef } = React;

const EMPTY_PROMPTS = [
  "What would you like to know about UR?",
  "Ask me anything about UR.",
  "Curious about student life? Ask away.",
  "Got a question about UR? I'm here.",
  "What can I help you with today?",
  "Wondering about majors or research? Just ask.",
  "Ask me anything, academics, housing, dining.",
  "Not sure where to start? Just ask.",
  "Looking for info about UR? I've got you.",
  "Academics or campus life? Ask away.",
];

const randomPrompt = EMPTY_PROMPTS[Math.floor(Math.random() * EMPTY_PROMPTS.length)];
const sessionId = crypto.randomUUID();

function Chatbot() {
  const [messages, setMessages] = useState([]);
  const [input, setInput]       = useState("");
  const [loading, setLoading]   = useState(false);
  const [isFirstLoad, setIsFirstLoad] = useState(true);
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
        body:    JSON.stringify({ question, history, session_id: sessionId }),
      });
      const data = await res.json();
      setMessages((prev) => [...prev, { role: "assistant", text: data.answer }]);
      setIsFirstLoad(false);
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", text: "Something went wrong. Please try again." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen flex flex-col" style={{height: "100dvh"}}>

      {/* Fixed top bar */}
      <div className="fixed top-0 left-0 right-0 bg-white border-b border-slate-200 px-4 sm:px-8 py-3 z-10 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <a href="https://www.rochester.edu/" target="_blank" rel="noreferrer">
            <img src="./logo.png" alt="University of Rochester" className="h-10" />
          </a>
          <span className="text-slate-300 text-base font-light">|</span>
          <span className="text-slate-600 text-xs font-medium tracking-wide uppercase">Chatbot</span>
        </div>
        <a href="https://github.com/sotamatsuda19/UR_chatbot" target="_blank" rel="noreferrer" className="text-slate-400 hover:text-slate-700 transition-colors">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
            <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
          </svg>
        </a>
      </div>

      {/* Chat area — pushed below the fixed bar */}
      <div className="flex flex-col flex-1 w-full max-w-2xl mx-auto px-4 pt-20">

        {isEmpty ? (
          /* ── Empty state: input centered vertically ── */
          <div className="flex flex-col justify-center flex-1 gap-8">
            <div className="flex flex-col gap-2">
              <p className="text-center text-slate-600 text-lg sm:text-xl font-medium">{randomPrompt}</p>
              <p className="text-center text-xs text-slate-400">
                An unofficial, student-led project — not affiliated with the University of Rochester.
              </p>
            </div>
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
            <div className="flex-1 overflow-y-auto pt-4 pb-4 space-y-4">
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
                <div className="fade-up flex flex-col gap-2">
                  <div className="flex justify-start">
                    <div className="message-bubble bg-slate-100 px-4 py-3 rounded-2xl rounded-bl-sm flex gap-1 items-center">
                      <span className="dot w-2 h-2 bg-slate-400 rounded-full inline-block"></span>
                      <span className="dot w-2 h-2 bg-slate-400 rounded-full inline-block"></span>
                      <span className="dot w-2 h-2 bg-slate-400 rounded-full inline-block"></span>
                    </div>
                  </div>
                  {isFirstLoad && (
                    <p className="text-xs text-slate-400 text-left pl-1">
                      The server is waking up — your first response may take up to 30 seconds. Thanks for your patience!
                    </p>
                  )}
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
                className="flex-1 bg-slate-100 rounded-xl px-4 py-3 text-base text-slate-800 placeholder-slate-400 outline-none focus:ring-2 focus:ring-blue-300 disabled:opacity-50"
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
              An unofficial, student-led project — not affiliated with the University of Rochester. This chatbot can make mistakes; verify important information with official UR sources.
            </p>
          </>
        )}

      </div>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<Chatbot />);
