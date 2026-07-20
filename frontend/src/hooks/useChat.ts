"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/services/api";
import type {
  ChatMessage,
  ChatSession,
  ChatSessionMessage,
  LLMProfile,
  MemoryResult,
} from "@/types";

export type StreamTraceStep = { step: string; value: string };

export interface UseChatOptions {
  sessionId: string | null;
  profileId: string;
  spaceName: string;
  searchStrategy: "auto" | "holistic" | "text_only" | "graph_only";
  topK: number;
  useRerank: boolean;
  saveToSpace: string;
  /**
   * 关闭上游 reasoning 模型的 think 能力. 适用于:
   * - 长时间 thinking 后才出第一个字 (TTFT 过长)
   * - 已知会陷入 thinking 死循环的题目
   * 注意: ollama 部署可能不真正响应 (取决于版本),
   * 我们的代码会同时下发 /no_think system prompt 作为双保险.
   */
  disableThinking?: boolean;
}

export function useChat(opts: UseChatOptions) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [messages, setMessages] = useState<ChatSessionMessage[]>([]);
  const [profiles, setProfiles] = useState<LLMProfile[]>([]);
  const [spaces, setSpaces] = useState<string[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentTrace, setCurrentTrace] = useState<StreamTraceStep[]>([]);
  const [currentMemories, setCurrentMemories] = useState<MemoryResult[]>([]);
  const [currentThinking, setCurrentThinking] = useState<string>("");
  const abortRef = useRef<AbortController | null>(null);

  // 加载 profiles
  const refreshProfiles = useCallback(async () => {
    try {
      const list = await api.get<LLMProfile[]>("llm/profiles");
      setProfiles(list || []);
    } catch {
      setProfiles([]);
    }
  }, []);

  // 加载 sessions
  const refreshSessions = useCallback(async () => {
    try {
      const list = await api.get<ChatSession[]>("chat/sessions");
      setSessions(list || []);
    } catch {
      setSessions([]);
    }
  }, []);

  // 加载 spaces
  const refreshSpaces = useCallback(async () => {
    try {
      // 复用 spaces 列表接口
      const list = await api.get<{ name: string }[]>("memory/spaces");
      setSpaces((list || []).map((s) => s.name));
    } catch {
      // 失败时给一些默认
      setSpaces(["base_memory"]);
    }
  }, []);

  // 加载消息
  const refreshMessages = useCallback(async (sid: string | null) => {
    if (!sid) {
      setMessages([]);
      return;
    }
    try {
      const sess = await api.get<ChatSession & { messages: ChatSessionMessage[] }>(
        `chat/sessions/${sid}`,
      );
      setMessages(sess.messages || []);
    } catch (err) {
      setError(`加载会话失败: ${(err as Error).message}`);
    }
  }, []);

  useEffect(() => {
    refreshProfiles();
    refreshSessions();
    refreshSpaces();
  }, [refreshProfiles, refreshSessions, refreshSpaces]);

  useEffect(() => {
    if (opts.sessionId) {
      refreshMessages(opts.sessionId);
    } else {
      setMessages([]);
    }
  }, [opts.sessionId, refreshMessages]);

  // 创建会话
  const createSession = useCallback(
    async (
      payload: Partial<ChatSession> & { title?: string } = {},
    ): Promise<ChatSession | null> => {
      try {
        const sess = await api.post<ChatSession>("chat/sessions", {
          title: payload.title || "新会话",
          profile_id: payload.profile_id ?? opts.profileId ?? "",
          space_name: payload.space_name ?? opts.spaceName ?? "",
          search_strategy: payload.search_strategy ?? opts.searchStrategy ?? "auto",
          top_k: payload.top_k ?? opts.topK ?? 5,
          use_rerank: payload.use_rerank ?? opts.useRerank ?? true,
          save_to_space: payload.save_to_space ?? opts.saveToSpace ?? "",
        });
        await refreshSessions();
        return sess;
      } catch (err) {
        setError(`创建会话失败: ${(err as Error).message}`);
        return null;
      }
    },
    [
      opts.profileId,
      opts.spaceName,
      opts.searchStrategy,
      opts.topK,
      opts.useRerank,
      opts.saveToSpace,
      refreshSessions,
    ],
  );

  // 删除会话
  const deleteSession = useCallback(
    async (sid: string) => {
      try {
        await api.del(`chat/sessions/${sid}`);
        await refreshSessions();
      } catch (err) {
        setError(`删除会话失败: ${(err as Error).message}`);
      }
    },
    [refreshSessions],
  );

  // 批量删除会话
  const batchDeleteSessions = useCallback(
    async (sids: string[]) => {
      if (sids.length === 0) return { deleted: [], missing: [], count: 0 };
      try {
        const result = await api.post<{ deleted: string[]; missing: string[]; count: number }>(
          "chat/sessions/batch-delete",
          { session_ids: sids },
        );
        await refreshSessions();
        return result;
      } catch (err) {
        setError(`批量删除失败: ${(err as Error).message}`);
        return { deleted: [], missing: sids, count: 0 };
      }
    },
    [refreshSessions],
  );

  // 更新会话
  const patchSession = useCallback(
    async (sid: string, fields: Partial<ChatSession>) => {
      try {
        const updated = await api.patch<ChatSession>(`chat/sessions/${sid}`, fields);
        await refreshSessions();
        return updated;
      } catch (err) {
        setError(`更新会话失败: ${(err as Error).message}`);
        return null;
      }
    },
    [refreshSessions],
  );

  // 停止当前生成
  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
  }, []);

  // 流式发送
  const sendMessage = useCallback(
    async (
      message: string,
      overrides: Partial<UseChatOptions> = {},
    ): Promise<void> => {
      if (!message.trim() || isStreaming) return;
      setError(null);
      setCurrentTrace([]);
      setCurrentMemories([]);
      const sid = overrides.sessionId ?? opts.sessionId;
      if (!sid) {
        setError("请先选择或新建会话");
        return;
      }
      const ac = new AbortController();
      abortRef.current = ac;
      setIsStreaming(true);

      // 立即把 user 消息插入
      const tempUser: ChatSessionMessage = {
        id: -Date.now(),
        role: "user",
        content: message,
        memories: [],
        thinking: null,
        trace: [],
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, tempUser]);

      const tempAssistant: ChatSessionMessage = {
        id: -Date.now() - 1,
        role: "assistant",
        content: "",
        memories: [],
        thinking: null,
        trace: [],
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, tempAssistant]);
      setCurrentTrace([]);
      setCurrentMemories([]);
      setCurrentThinking("");

      try {
        const resp = await fetch("/api/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sid,
            message,
            profile_id: overrides.profileId ?? opts.profileId ?? "",
            space_name: overrides.spaceName ?? opts.spaceName ?? "",
            search_strategy: overrides.searchStrategy ?? opts.searchStrategy ?? "auto",
            top_k: overrides.topK ?? opts.topK ?? 5,
            use_rerank: overrides.useRerank ?? opts.useRerank ?? true,
            save_to_space: overrides.saveToSpace ?? opts.saveToSpace ?? "",
            context_token_budget: 3000,
            // 关闭 reasoning 模型的 think 能力 (vllm 部署立即生效; ollama 走 /no_think 引导)
            disable_thinking: overrides.disableThinking ?? opts.disableThinking ?? false,
          }),
          signal: ac.signal,
        });
        if (!resp.ok || !resp.body) {
          const text = await resp.text();
          throw new Error(`HTTP ${resp.status}: ${text.slice(0, 200)}`);
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        // 重新拉一次最新消息以拿到真实 id
        let assistantId = tempAssistant.id;
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          // SSE 解析：\n\n 分隔
          let idx: number;
          while ((idx = buffer.indexOf("\n\n")) >= 0) {
            const raw = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);
            const lines = raw.split("\n");
            let event = "message";
            let dataStr = "";
            for (const line of lines) {
              if (line.startsWith("event:")) event = line.slice(6).trim();
              else if (line.startsWith("data:")) dataStr += line.slice(5).trim();
            }
            if (!dataStr) continue;
            let data: any = dataStr;
            try {
              data = JSON.parse(dataStr);
            } catch {
              /* keep as string */
            }
            if (event === "trace") {
              setCurrentTrace((prev) => [
                ...prev,
                {
                  step: data.step || "",
                  value: data.value || "",
                  uid: data.uid,
                  title: data.title,
                  snippet: data.snippet,
                  score: data.score,
                },
              ]);
            } else if (event === "hit") {
              setCurrentMemories((prev) => {
                if (prev.find((m) => m.uid === data.uid)) return prev;
                return [...prev, data as MemoryResult];
              });
            } else if (event === "token") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: m.content + (data.content || "") }
                    : m,
                ),
              );
            } else if (event === "thinking") {
              setCurrentThinking((prev) => prev + (data.content || ""));
            } else if (event === "done") {
              // 1) 先用 done 内的真实 answer 覆盖临时消息（避免模型在 streaming 末尾不输出 token 的情况）
              if (typeof data.answer === "string") {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: data.answer || m.content }
                      : m,
                  ),
                );
              }
              // 2) 落库后用真实 id 替换临时消息
              await refreshMessages(sid);
              await refreshSessions();
              setIsStreaming(false);
              abortRef.current = null;
              return;
            } else if (event === "error") {
              setError(typeof data === "string" ? data : data.message || "生成失败");
            }
          }
        }
        // 兜底
        await refreshMessages(sid);
        await refreshSessions();
      } catch (err) {
        const e = err as Error;
        if (e.name === "AbortError") {
          setError("已停止生成");
        } else {
          setError(e.message);
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [opts, isStreaming, refreshMessages, refreshSessions],
  );

  // 保存指定消息为记忆
  const saveMessageToSpace = useCallback(
    async (messageId: number, spaceName: string) => {
      if (!opts.sessionId) return;
      try {
        await api.post<{ status: string; uid: string }>("chat/save-to-space", {
          session_id: opts.sessionId,
          message_id: messageId,
          space_name: spaceName,
        });
      } catch (err) {
        setError(`保存失败: ${(err as Error).message}`);
      }
    },
    [opts.sessionId],
  );

  // 重命名会话
  const renameSession = useCallback(
    async (sid: string, title: string) => {
      return patchSession(sid, { title });
    },
    [patchSession],
  );

  return {
    sessions,
    messages,
    profiles,
    spaces,
    isStreaming,
    error,
    currentTrace,
    currentMemories,
    currentThinking,
    refreshSessions,
    refreshMessages,
    refreshProfiles,
    refreshSpaces,
    createSession,
    deleteSession,
    batchDeleteSessions,
    patchSession,
    renameSession,
    sendMessage,
    saveMessageToSpace,
    stop,
  };
}

export type ChatMessageShape = ChatMessage;
