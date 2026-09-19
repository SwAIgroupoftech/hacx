import React from "react";

type Message = {
  id: number;
  role: "assistant" | "user";
  text: string;
};

export function FloatingTrafficChat() {
  const [open, setOpen] = React.useState(false);
  const [input, setInput] = React.useState("");

  const [messages, setMessages] = React.useState<Message[]>([
    {
      id: 1,
      role: "assistant",
      text: "TrafficSense intelligence console ready. Ask about congestion, incidents, forecasts, or bottlenecks.",
    },
  ]);

  const suggestions = [
    "Why is the North Corridor congested?",
    "What is expected over the next 30 minutes?",
    "Which bottlenecks are recurring?",
  ];

  function sendMessage(text = input) {
    const trimmed = text.trim();

    if (!trimmed) return;

    setMessages((current) => [
      ...current,
      {
        id: Date.now(),
        role: "user",
        text: trimmed,
      },
      {
        id: Date.now() + 1,
        role: "assistant",
        text: "Demo response: TrafficSense would retrieve the relevant evidence packet, segment history, forecast data, and validation metadata here.",
      },
    ]);

    setInput("");
  }

  return (
    <>
      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-24 right-5 z-[100] flex w-[380px] max-w-[calc(100vw-32px)] flex-col overflow-hidden border border-white/10 bg-[#101010] shadow-2xl shadow-black/50">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-red-700" />

                <span className="text-sm font-semibold text-white">
                  Ask TrafficSense
                </span>
              </div>

              <div className="mt-1 text-[10px] tracking-wide text-neutral-500">
                EVIDENCE-BASED TRAFFIC INTELLIGENCE
              </div>
            </div>

            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close TrafficSense assistant"
              className="flex h-7 w-7 items-center justify-center text-lg text-neutral-500 transition hover:bg-white/5 hover:text-white"
            >
              ×
            </button>
          </div>

          {/* Messages */}
          <div className="max-h-[330px] min-h-[230px] space-y-4 overflow-y-auto p-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={
                  message.role === "user"
                    ? "ml-8"
                    : "mr-5"
                }
              >
                <div
                  className={
                    message.role === "user"
                      ? "border border-white/10 bg-white/[0.06] px-3 py-2 text-sm text-neutral-200"
                      : "border-l-2 border-red-800/70 pl-3 text-sm leading-6 text-neutral-300"
                  }
                >
                  {message.text}
                </div>

                {message.role === "assistant" && (
                  <div className="mt-1 text-[9px] tracking-wider text-neutral-600">
                    TRAFFICSENSE · DEMO
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Suggested questions */}
          {messages.length === 1 && (
            <div className="border-t border-white/10 px-4 py-3">
              <div className="mb-2 text-[9px] tracking-[0.18em] text-neutral-600">
                SUGGESTED QUESTIONS
              </div>

              <div className="space-y-1.5">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => sendMessage(suggestion)}
                    className="block w-full border border-white/10 px-3 py-2 text-left text-[11px] text-neutral-400 transition hover:border-white/20 hover:bg-white/[0.04] hover:text-white"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input */}
          <div className="border-t border-white/10 p-3">
            <div className="flex items-center gap-2 border border-white/10 bg-black/30 px-3 py-2">
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    sendMessage();
                  }
                }}
                placeholder="Ask about the network..."
                className="min-w-0 flex-1 bg-transparent text-xs text-white outline-none placeholder:text-neutral-600"
              />

              <button
                type="button"
                onClick={() => sendMessage()}
                aria-label="Send question"
                className="text-xs font-medium text-neutral-300 transition hover:text-white"
              >
                SEND
              </button>
            </div>

            <div className="mt-2 text-center text-[9px] text-neutral-600">
              ADVISORY ONLY · SIMULATED
            </div>
          </div>
        </div>
      )}

      {/* Floating button */}
      <div className="fixed bottom-5 right-5 z-[100]">
        <button
          type="button"
          onClick={() => setOpen((current) => !current)}
          aria-label={
            open
              ? "Close Ask TrafficSense"
              : "Open Ask TrafficSense"
          }
          className="group flex items-center gap-3 border border-white/15 bg-[#151515] px-3 py-3 shadow-xl shadow-black/40 transition duration-200 hover:border-white/25 hover:bg-[#1b1b1b]"
        >
          <span className="hidden text-left sm:block">
            <span className="block text-[11px] font-medium text-white">
              Ask TrafficSense
            </span>

            <span className="block text-[9px] tracking-wider text-neutral-600">
              AI TRAFFIC INTELLIGENCE
            </span>
          </span>

          <span className="flex h-9 w-9 items-center justify-center border border-white/10 bg-black text-sm text-neutral-300 transition group-hover:text-white">
            {open ? "×" : "✦"}
          </span>
        </button>
      </div>
    </>
  );
}