"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { Pill } from "@/components/shared/Pill";
import { EmptyState } from "@/components/shared/EmptyState";
import { MarkdownRenderer } from "@/components/shared/MarkdownRenderer";
import { useChat } from "@/hooks/useChat";
import type { AgentInfo, ChatMessage } from "@/types";

function MessageBubble({
  msg,
  agent,
}: {
  msg: ChatMessage;
  agent?: AgentInfo;
}) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex gap-4 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={[
          "w-8 h-8 rounded flex items-center justify-center flex-shrink-0 mt-1",
          isUser ? "bg-primary" : "bg-surface-container-high",
        ].join(" ")}
      >
        <Icon
          name={isUser ? "person" : "smart_toy"}
          filled
          className={`text-[18px] ${isUser ? "text-on-primary" : "text-primary"}`}
        />
      </div>
      <div className={`space-y-2 max-w-[80%] ${isUser ? "items-end" : ""}`}>
        {/* Memories cited */}
        {!isUser && msg.memories && msg.memories.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {msg.memories.slice(0, 4).map((m) => (
              <a
                key={m.rel_path}
                href={`/memory/${encodeURIComponent(m.rel_path)}`}
                className="inline-flex items-center gap-1 px-2 py-0.5 bg-primary-fixed border border-primary/20 rounded-full text-label-sm text-primary hover:opacity-80"
              >
                <Icon name="link" className="text-[12px]" />
                {m.title || m.rel_path.split("/").pop()}
              </a>
            ))}
            {msg.memories.length > 4 && (
              <Pill variant="primary" size="sm">
                +{msg.memories.length - 4} more
              </Pill>
            )}
          </div>
        )}

        {/* Thinking indicator */}
        {!isUser && msg.thinking && (
          <details className="bg-surface-container-low border border-border rounded-lg px-3 py-2">
            <summary className="text-label-md text-on-surface-variant cursor-pointer flex items-center gap-1.5">
              <Icon name="psychology" className="text-[14px]" />
              Reasoning trace
            </summary>
            <p className="mt-2 text-body-sm text-on-surface-variant italic whitespace-pre-wrap">
              {msg.thinking}
            </p>
          </details>
        )}

        {/* Message body */}
        <div
          className={[
            "p-4 rounded-xl",
            isUser
              ? "bg-primary text-on-primary"
              : "bg-surface-container-low border border-border text-on-surface",
          ].join(" ")}
        >
          {msg.streaming && !msg.content ? (
            <div className="flex items-center gap-1.5 py-1">
              <span className="w-2 h-2 bg-on-surface-variant rounded-full thinking-dot" />
              <span
                className="w-2 h-2 bg-on-surface-variant rounded-full thinking-dot"
                style={{ animationDelay: "0.2s" }}
              />
              <span
                className="w-2 h-2 bg-on-surface-variant rounded-full thinking-dot"
                style={{ animationDelay: "0.4s" }}
              />
            </div>
          ) : isUser ? (
            <p className="font-body-md whitespace-pre-wrap">{msg.content}</p>
          ) : (
            <MarkdownRenderer content={msg.content} />
          )}
        </div>
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<Loading size="lg" label="Loading chat..." />}>
      <ChatContent />
    </Suspense>
  );
}

function ChatContent() {
  const searchParams = useSearchParams();
  const initialAgent = searchParams.get("agent") || "codex-architect";
  const [agentId, setAgentId] = useState(initialAgent);
  const [input, setInput] = useState("");
  const { messages, agents, isStreaming, error, sendMessage, clearMessages } =
    useChat(agentId);
  const [showAgentPicker, setShowAgentPicker] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const currentAgent = agents.find((a) => a.id === agentId);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    sendMessage(input.trim());
    setInput("");
  };

  return (
    <AppShell
      title={currentAgent?.name || "Chat"}
      subtitle={currentAgent?.role}
      rightSlot={
        <button
          onClick={clearMessages}
          className="p-2 text-on-surface-variant hover:text-error transition-colors"
          title="Clear conversation"
        >
          <Icon name="delete_sweep" />
        </button>
      }
    >
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Agent picker bar */}
        <div className="border-b border-border px-panel-padding py-2 flex items-center gap-3 bg-surface">
          <div className="relative">
            <button
              onClick={() => setShowAgentPicker(!showAgentPicker)}
              className="flex items-center gap-2 px-3 py-1.5 border border-border rounded-lg hover:bg-surface-container-low transition-colors"
            >
              <Icon name="neurology" filled className="text-[20px] text-primary" />
              <span className="text-body-md font-medium">
                {currentAgent?.name || "Select agent"}
              </span>
              <Icon name="expand_more" className="text-[18px]" />
            </button>
            {showAgentPicker && (
              <div className="absolute top-full mt-1 left-0 bg-surface border border-border rounded-lg shadow-lg z-50 min-w-[280px]">
                {agents.map((a) => (
                  <button
                    key={a.id}
                    onClick={() => {
                      setAgentId(a.id);
                      setShowAgentPicker(false);
                    }}
                    className={[
                      "w-full text-left px-3 py-2 hover:bg-surface-container-low transition-colors flex items-start gap-2 border-b border-border last:border-b-0",
                      a.id === agentId ? "bg-primary-fixed/50" : "",
                    ].join(" ")}
                  >
                    <Icon
                      name="smart_toy"
                      filled
                      className="text-[18px] text-primary mt-0.5"
                    />
                    <div>
                      <p className="text-body-md font-bold text-on-surface">
                        {a.name}
                      </p>
                      <p className="text-label-sm text-on-surface-variant">
                        {a.role}
                      </p>
                    </div>
                  </button>
                ))}
                {agents.length === 0 && (
                  <p className="px-3 py-2 text-body-sm text-on-surface-variant">
                    No agents configured.
                  </p>
                )}
              </div>
            )}
          </div>
          {currentAgent && (
            <div className="flex items-center gap-2">
              <Pill variant="info" size="sm">
                {currentAgent.llm_provider}
              </Pill>
              <Pill size="sm">{currentAgent.memory_strategy}</Pill>
              <span className="text-label-sm text-on-surface-variant">
                Limit: {currentAgent.memory_limit}
              </span>
            </div>
          )}
        </div>

        {/* Messages */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto custom-scrollbar px-12 py-8"
        >
          <div className="max-w-[1000px] mx-auto space-y-8">
            {messages.length === 0 && (
              <EmptyState
                icon="smart_toy"
                title="Start a conversation"
                description={
                  currentAgent
                    ? `${currentAgent.name} is ready. Ask anything about your memories.`
                    : "Select an agent to start chatting."
                }
              />
            )}

            {messages.map((msg, i) => (
              <MessageBubble key={i} msg={msg} agent={currentAgent} />
            ))}

            {error && (
              <div className="bg-error/10 border border-error/20 text-error rounded-lg p-3 flex items-center gap-2">
                <Icon name="error" filled />
                <span className="text-body-md">{error}</span>
              </div>
            )}
          </div>
        </div>

        {/* Composer */}
        <div className="border-t border-border px-panel-padding py-4 bg-surface">
          <form
            onSubmit={onSubmit}
            className="max-w-[1000px] mx-auto flex items-end gap-2"
          >
            <div className="flex-1 relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    onSubmit(e);
                  }
                }}
                placeholder="Ask your agent... (Enter to send, Shift+Enter for newline)"
                rows={1}
                className="w-full px-4 py-3 bg-surface-container-low border border-border rounded-xl focus:ring-2 focus:ring-primary focus:border-primary outline-none text-body-md resize-none max-h-32"
                style={{ minHeight: "48px" }}
              />
            </div>
            <button
              type="submit"
              disabled={!input.trim() || isStreaming}
              className="px-4 py-3 bg-primary text-on-primary rounded-xl font-bold hover:opacity-90 transition-opacity disabled:opacity-40 flex items-center gap-2"
            >
              {isStreaming ? (
                <Loading size="sm" />
              ) : (
                <Icon name="send" className="text-[20px]" />
              )}
              Send
            </button>
          </form>
        </div>
      </div>
    </AppShell>
  );
}
