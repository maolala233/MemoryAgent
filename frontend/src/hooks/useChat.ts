"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { wsUrl } from "@/services/api";
import { api, ApiError } from "@/services/api";
import type { AgentInfo, ChatMessage, MemoryResult } from "@/types";

export function useChat(agentId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    api.get<AgentInfo[]>("agents").then(setAgents).catch(() => setAgents([]));
  }, []);

  useEffect(() => {
    if (!agentId) return;
    api.get<ChatMessage[]>(`chat/history/${agentId}`).then(setMessages).catch(() => {
      // ignore
    });
  }, [agentId]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return wsRef.current;
    const ws = new WebSocket(wsUrl(`/api/chat/stream/${agentId}`));
    wsRef.current = ws;
    ws.onclose = () => {
      wsRef.current = null;
    };
    ws.onerror = () => {
      setError("WebSocket connection failed");
    };
    return ws;
  }, [agentId]);

  const sendMessage = useCallback(
    (message: string) => {
      setError(null);
      const ws = connect();
      setMessages((prev) => [...prev, { role: "user", content: message }]);
      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: "",
        streaming: true,
        memories: [],
        thinking: null,
      };
      setMessages((prev) => [...prev, assistantMsg]);

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.type === "memories") {
            const mems = data.content as MemoryResult[];
            setMessages((prev) => {
              const next = [...prev];
              next[next.length - 1] = { ...next[next.length - 1], memories: mems };
              return next;
            });
          } else if (data.type === "thinking") {
            setMessages((prev) => {
              const next = [...prev];
              next[next.length - 1] = { ...next[next.length - 1], thinking: data.content };
              return next;
            });
          } else if (data.type === "chunk") {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              next[next.length - 1] = { ...last, content: last.content + data.content };
              return next;
            });
          } else if (data.type === "done") {
            setIsStreaming(false);
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              next[next.length - 1] = { ...last, streaming: false };
              return next;
            });
          } else if (data.type === "error") {
            setIsStreaming(false);
            setError(data.content);
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onopen = () => {
        setIsStreaming(true);
        ws.send(JSON.stringify({ message, context: [] }));
      };
    },
    [connect],
  );

  const clearMessages = useCallback(() => setMessages([]), []);

  const sendSync = useCallback(
    async (message: string) => {
      setError(null);
      try {
        const data = await api.post<{
          response: string;
          memories_used: MemoryResult[];
          thinking: string | null;
          status: string;
        }>("chat", { message, agent: agentId });
        setMessages((prev) => [
          ...prev,
          { role: "user", content: message },
          {
            role: "assistant",
            content: data.response,
            memories: data.memories_used,
            thinking: data.thinking,
          },
        ]);
        return data;
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : "Chat failed");
        return null;
      }
    },
    [agentId],
  );

  useEffect(() => {
    return () => {
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, []);

  return {
    messages,
    agents,
    isStreaming,
    error,
    sendMessage,
    sendSync,
    clearMessages,
  };
}
