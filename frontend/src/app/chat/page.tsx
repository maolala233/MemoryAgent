"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { Pill } from "@/components/shared/Pill";
import { EmptyState } from "@/components/shared/EmptyState";
import { MarkdownRenderer } from "@/components/shared/MarkdownRenderer";
import { useChat } from "@/hooks/useChat";
import type { ChatSessionMessage, MemoryResult } from "@/types";

type Strategy = "auto" | "holistic" | "text_only" | "graph_only";

const STRATEGY_LABEL: Record<Strategy, string> = {
  auto: "自动多策略",
  holistic: "整体检索（向量+图谱+Rerank）",
  text_only: "纯向量文本",
  graph_only: "仅图谱",
};

function TracePanel({
  trace,
  thinking,
}: {
  trace: { step: string; value: string; uid?: string; title?: string; snippet?: string; score?: number }[];
  thinking?: string;
}) {
  if (trace.length === 0 && !thinking) return null;
  // 按 step 类别分组
  const profileLines = trace.filter((t) => t.step === "profile" || t.step === "query" || t.step === "start");
  const strategyLines = trace.filter((t) => t.step === "strategy" || t.step === "space_filter");
  const graphLines = trace.filter((t) => t.step === "graph_subgraph" || t.step === "graph_expand");
  const hitLines = trace.filter((t) => t.step === "hit");
  const ctxLines = trace.filter((t) => t.step === "context" || t.step === "hits_count");
  const genLines = trace.filter((t) => t.step === "generating");
  const saveLines = trace.filter((t) => t.step === "saved" || t.step === "save_error");
  const doneLines = trace.filter((t) => t.step === "done");
  const otherLines = trace.filter(
    (t) => !["profile", "query", "start", "strategy", "space_filter", "graph_subgraph", "graph_expand", "hit", "context", "hits_count", "generating", "saved", "save_error", "done", "error"].includes(t.step),
  );

  return (
    <details
      className="bg-surface-container-lowest border border-border rounded-lg px-3 py-2 text-label-sm"
      open
    >
      <summary className="cursor-pointer flex items-center gap-1.5 text-on-surface-variant">
        <Icon name="account_tree" className="text-[14px]" />
        执行过程（{trace.length} 步 / 命中 {hitLines.length} 条）
      </summary>

      <div className="mt-2 space-y-3">
        {/* 1. 配置 / 入口 */}
        {(profileLines.length > 0 || strategyLines.length > 0) && (
          <Section icon="settings" title="入口与策略">
            <ol className="space-y-1 pl-4 list-decimal text-on-surface-variant">
              {[...profileLines, ...strategyLines].map((t, i) => (
                <li key={i}>
                  <span className="text-primary font-medium">[{t.step}]</span> {t.value}
                </li>
              ))}
            </ol>
          </Section>
        )}

        {/* 1.5 图谱检索（图谱子图 + BFS 扩展） */}
        {graphLines.length > 0 && (
          <Section icon="hub" title={`图谱检索（${graphLines.length} 步）`}>
            <ol className="space-y-1 pl-4 list-decimal text-on-surface-variant">
              {graphLines.map((t, i) => (
                <li key={i}>
                  <span className="text-primary font-medium">[{t.step}]</span> {t.value}
                </li>
              ))}
            </ol>
          </Section>
        )}

        {/* 2. 命中详情（每条 hit 的 snippet+score） */}
        {hitLines.length > 0 && (
          <Section icon="target" title={`检索命中（${hitLines.length} 条）`}>
            <ol className="space-y-1.5 pl-4 list-decimal text-on-surface-variant">
              {hitLines.map((h, i) => {
                // 通过 uid 前缀/分数判断来源
                const isGraph = h.title?.includes("graph_bfs") || h.snippet?.includes("graph_bfs");
                const isRerank = h.score !== undefined && h.score > 0.5;
                const srcTag = isGraph ? "图谱扩展" : isRerank ? "向量+Rerank" : "向量检索";
                const srcColor = isGraph
                  ? "bg-tertiary-fixed text-tertiary"
                  : isRerank
                    ? "bg-primary-fixed text-primary"
                    : "bg-secondary-fixed text-secondary";
                return (
                  <li key={i}>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className={`px-1.5 py-0.5 rounded text-label-sm ${srcColor}`}>
                        {srcTag}
                      </span>
                      <span className="text-primary font-medium">{h.title || h.uid || `hit-${i + 1}`}</span>
                      {typeof h.score === "number" && (
                        <span className="px-1.5 py-0.5 bg-primary-fixed text-primary rounded text-label-sm">
                          score={h.score.toFixed(3)}
                        </span>
                      )}
                      {h.uid && (
                        <a
                          href={`/units?uid=${encodeURIComponent(h.uid)}`}
                          target="_blank"
                          rel="noreferrer"
                          className="text-label-sm text-primary hover:underline inline-flex items-center gap-0.5"
                        >
                          <Icon name="open_in_new" className="text-[12px]" /> 打开
                        </a>
                      )}
                    </div>
                    {h.snippet && (
                      <p className="mt-0.5 pl-1 text-on-surface-variant/80 line-clamp-2">
                        {h.snippet}
                      </p>
                    )}
                  </li>
                );
              })}
            </ol>
          </Section>
        )}

        {/* 3. 上下文构造 */}
        {ctxLines.length > 0 && (
          <Section icon="memory" title="上下文">
            <ol className="space-y-1 pl-4 list-decimal text-on-surface-variant">
              {ctxLines.map((t, i) => (
                <li key={i}>
                  <span className="text-primary font-medium">[{t.step}]</span> {t.value}
                </li>
              ))}
            </ol>
          </Section>
        )}

        {/* 4. 生成过程（含 thinking 折叠） */}
        {(genLines.length > 0 || thinking) && (
          <Section icon="auto_awesome" title="模型推理">
            <ol className="space-y-1 pl-4 list-decimal text-on-surface-variant">
              {genLines.map((t, i) => (
                <li key={i}>
                  <span className="text-primary font-medium">[{t.step}]</span> {t.value}
                </li>
              ))}
            </ol>
            {thinking && (
              <details className="mt-2 ml-2">
                <summary className="cursor-pointer text-on-surface-variant/80 hover:text-on-surface inline-flex items-center gap-1">
                  <Icon name="psychology" className="text-[14px]" />
                  思考过程（{thinking.length} 字）
                </summary>
                <pre className="mt-1 ml-2 p-2 bg-surface-container rounded text-label-sm text-on-surface-variant whitespace-pre-wrap max-h-40 overflow-y-auto custom-scrollbar">
                  {thinking}
                </pre>
              </details>
            )}
          </Section>
        )}

        {/* 5. 落库 / 完成 */}
        {(saveLines.length > 0 || doneLines.length > 0) && (
          <Section icon="check_circle" title="落库与完成">
            <ol className="space-y-1 pl-4 list-decimal text-on-surface-variant">
              {[...saveLines, ...doneLines].map((t, i) => (
                <li key={i}>
                  <span className="text-primary font-medium">[{t.step}]</span> {t.value}
                </li>
              ))}
            </ol>
          </Section>
        )}

        {/* 6. 其他 */}
        {otherLines.length > 0 && (
          <Section icon="more_horiz" title="其他">
            <ol className="space-y-1 pl-4 list-decimal text-on-surface-variant">
              {otherLines.map((t, i) => (
                <li key={i}>
                  <span className="text-primary font-medium">[{t.step}]</span> {t.value}
                </li>
              ))}
            </ol>
          </Section>
        )}
      </div>
    </details>
  );
}

function Section({
  icon,
  title,
  children,
}: {
  icon: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5 text-on-surface font-medium">
        <Icon name={icon} className="text-[14px] text-primary" />
        {title}
      </div>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function MemoryChips({ memories }: { memories: MemoryResult[] }) {
  if (!memories || memories.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {memories.slice(0, 8).map((m, i) => {
        const label = m.uid || m.title || m.rel_path?.split("/").pop() || `记忆${i + 1}`;
        const href = m.uid ? `/units?uid=${encodeURIComponent(m.uid)}` : `/memory/${encodeURIComponent(m.rel_path)}`;
        return (
          <a
            key={i}
            href={href}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 px-2 py-0.5 bg-primary-fixed border border-primary/20 rounded-full text-label-sm text-primary hover:opacity-80 max-w-[240px] truncate"
            title={m.text || m.snippet || label}
          >
            <Icon name="link" className="text-[12px]" />
            <span className="truncate">{label}</span>
          </a>
        );
      })}
      {memories.length > 8 && (
        <Pill variant="primary" size="sm">+{memories.length - 8} 更多</Pill>
      )}
    </div>
  );
}

function MessageBubble({
  msg,
  isStreaming,
  streamingMemories,
  streamingTrace,
  streamingThinking,
  onSave,
  spaces,
}: {
  msg: ChatSessionMessage;
  isStreaming?: boolean;
  streamingMemories?: MemoryResult[];
  streamingTrace?: { step: string; value: string; uid?: string; title?: string; snippet?: string; score?: number }[];
  streamingThinking?: string;
  onSave?: (msgId: number, space: string) => void;
  spaces: string[];
}) {
  const isUser = msg.role === "user";
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveSpace, setSaveSpace] = useState(spaces[0] || "");
  const memories = isUser
    ? (msg.memories || [])
    : (isStreaming && msg.content === "" ? streamingMemories : msg.memories) || [];
  const rawTrace = isStreaming && msg.content === "" ? streamingTrace || [] : msg.trace || [];
  const trace = (rawTrace as Array<Record<string, unknown>>)
    .map((t) => ({
      step: String(t.step || ""),
      value: String(t.value || ""),
      uid: t.uid as string | undefined,
      title: t.title as string | undefined,
      snippet: t.snippet as string | undefined,
      score: typeof t.score === "number" ? (t.score as number) : undefined,
    }))
    .filter((t) => t.step);
  const displayThinking = isStreaming && msg.content === ""
    ? (streamingThinking || msg.thinking || "")
    : (msg.thinking || "");

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
        {/* 记忆引用 */}
        {!isUser && memories.length > 0 && (
          <MemoryChips memories={memories} />
        )}
        {/* 过程（仅 assistant 第一次生成时显示） */}
        {!isUser && trace.length > 0 && (
          <TracePanel trace={trace} thinking={displayThinking} />
        )}
        <div
          className={[
            "p-4 rounded-xl",
            isUser
              ? "bg-primary text-on-primary"
              : "bg-surface-container-low border border-border text-on-surface",
          ].join(" ")}
        >
          {isUser ? (
            <p className="font-body-md whitespace-pre-wrap">{msg.content}</p>
          ) : !msg.content && isStreaming ? (
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
          ) : (
            <MarkdownRenderer content={msg.content} />
          )}
        </div>

        {/* 操作按钮：仅 assistant 完整消息可保存到空间 */}
        {!isUser && msg.content && !isStreaming && onSave && msg.id > 0 && spaces.length > 0 && (
          <div className="flex items-center gap-2">
            {!saveOpen ? (
              <button
                onClick={() => setSaveOpen(true)}
                className="text-label-sm text-primary inline-flex items-center gap-1 hover:underline"
              >
                <Icon name="bookmark_add" className="text-[14px]" />
                保存到空间
              </button>
            ) : (
              <div className="flex items-center gap-1.5">
                <select
                  value={saveSpace}
                  onChange={(e) => setSaveSpace(e.target.value)}
                  className="px-2 py-1 text-label-sm border border-border rounded bg-surface"
                >
                  {spaces.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <button
                  onClick={() => {
                    onSave(msg.id, saveSpace);
                    setSaveOpen(false);
                  }}
                  className="px-2 py-1 text-label-sm bg-primary text-on-primary rounded"
                >
                  保存
                </button>
                <button
                  onClick={() => setSaveOpen(false)}
                  className="px-2 py-1 text-label-sm border border-border rounded"
                >
                  取消
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<Loading size="lg" label="加载对话中..." />}>
      <ChatContent />
    </Suspense>
  );
}

function ChatContent() {
  const searchParams = useSearchParams();
  const initialSpace = searchParams.get("space") || "";

  // 会话状态
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showSidebar, setShowSidebar] = useState(true);
  const [batchMode, setBatchMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // 配置
  const [profileId, setProfileId] = useState("");
  const [spaceName, setSpaceName] = useState(initialSpace);
  const [strategy, setStrategy] = useState<Strategy>("auto");
  const [topK, setTopK] = useState(5);
  const [useRerank, setUseRerank] = useState(true);
  const [saveToSpace, setSaveToSpace] = useState("");
  const [showSettings, setShowSettings] = useState(true);

  const chat = useChat({
    sessionId,
    profileId,
    spaceName,
    searchStrategy: strategy,
    topK,
    useRerank,
    saveToSpace,
  });

  // 选择会话时同步它的配置
  useEffect(() => {
    const s = chat.sessions.find((x) => x.id === sessionId);
    if (s) {
      setProfileId(s.profile_id);
      setSpaceName(s.space_name);
      setStrategy((s.search_strategy as Strategy) || "auto");
      setTopK(s.top_k);
      setUseRerank(s.use_rerank);
      setSaveToSpace(s.save_to_space);
    }
  }, [sessionId, chat.sessions]);

  // 默认 profile
  useEffect(() => {
    if (!profileId && chat.profiles.length > 0) {
      const def = chat.profiles.find((p) => p.is_default && p.enabled) || chat.profiles.find((p) => p.enabled);
      if (def) setProfileId(def.id);
    }
  }, [chat.profiles, profileId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [chat.messages, chat.isStreaming]);

  // 新建对话
  const handleNewSession = async () => {
    const sess = await chat.createSession({ title: "新会话" });
    if (sess) setSessionId(sess.id);
  };

  // 切换会话
  const handleSelectSession = (sid: string) => {
    setSessionId(sid);
  };

  // 删除会话
  const handleDeleteSession = async (sid: string) => {
    if (!confirm("确定删除该会话及其所有消息？")) return;
    await chat.deleteSession(sid);
    if (sessionId === sid) setSessionId(null);
  };

  // 批量选择
  const toggleSelect = (sid: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(sid)) next.delete(sid);
      else next.add(sid);
      return next;
    });
  };

  // 批量删除
  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return;
    if (!confirm(`确定删除所选 ${selectedIds.size} 个会话及其所有消息？`)) return;
    const sids = Array.from(selectedIds);
    const result = await chat.batchDeleteSessions(sids);
    if (sessionId && sids.includes(sessionId)) setSessionId(null);
    setSelectedIds(new Set());
    setBatchMode(false);
    if (result.missing.length > 0) {
      alert(`已删除 ${result.count} 个，${result.missing.length} 个未找到。`);
    }
  };

  const currentSession = useMemo(
    () => chat.sessions.find((s) => s.id === sessionId) || null,
    [chat.sessions, sessionId],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || chat.isStreaming) return;
    let sid = sessionId;
    if (!sid) {
      // 自动建一个
      chat.createSession({ title: input.slice(0, 30) }).then((s) => {
        if (s) {
          setSessionId(s.id);
          // 等 sessionId 更新后再 send
          setTimeout(() => chat.sendMessage(input.trim()), 50);
        }
      });
      setInput("");
      return;
    }
    chat.sendMessage(input.trim());
    setInput("");
  };

  const onSaveMessage = (msgId: number, space: string) => {
    chat.saveMessageToSpace(msgId, space);
  };

  return (
    <AppShell
      title={currentSession?.title || "知识问答"}
      subtitle={
        currentSession
          ? `会话 ${currentSession.id.slice(0, 8)} · ${chat.sessions.length} 个会话`
          : "基于记忆的智能问答 · 支持多模型多策略"
      }
      rightSlot={
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowSidebar(!showSidebar)}
            className="p-2 text-on-surface-variant hover:text-primary transition-colors"
            title="切换侧栏"
          >
            <Icon name={showSidebar ? "view_sidebar" : "view_stream"} />
          </button>
        </div>
      }
    >
      <div className="flex-1 flex h-full overflow-hidden">
        {/* 左侧：会话历史 */}
        {showSidebar && (
          <div className="w-72 border-r border-border bg-surface flex flex-col">
            <div className="p-3 border-b border-border flex items-center justify-between">
              {batchMode ? (
                <>
                  <span className="text-body-md font-medium">
                    已选 {selectedIds.size}
                  </span>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => {
                        if (selectedIds.size === chat.sessions.length) {
                          setSelectedIds(new Set());
                        } else {
                          setSelectedIds(new Set(chat.sessions.map((s) => s.id)));
                        }
                      }}
                      className="p-1.5 text-on-surface-variant hover:bg-surface-container rounded text-label-sm"
                      title="全选/取消全选"
                    >
                      <Icon name={selectedIds.size === chat.sessions.length ? "deselect" : "done_all"} />
                    </button>
                    <button
                      onClick={handleBatchDelete}
                      disabled={selectedIds.size === 0}
                      className="p-1.5 text-error hover:bg-error-fixed rounded disabled:opacity-40"
                      title="删除所选"
                    >
                      <Icon name="delete" />
                    </button>
                    <button
                      onClick={() => {
                        setBatchMode(false);
                        setSelectedIds(new Set());
                      }}
                      className="p-1.5 text-on-surface-variant hover:bg-surface-container rounded"
                      title="退出批量"
                    >
                      <Icon name="close" />
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <span className="text-body-md font-medium">对话历史</span>
                  <div className="flex items-center gap-1">
                    {chat.sessions.length > 0 && (
                      <button
                        onClick={() => setBatchMode(true)}
                        className="p-1.5 text-on-surface-variant hover:bg-surface-container rounded"
                        title="批量管理"
                      >
                        <Icon name="checklist" />
                      </button>
                    )}
                    <button
                      onClick={handleNewSession}
                      className="p-1.5 text-primary hover:bg-primary-fixed rounded"
                      title="新建对话"
                    >
                      <Icon name="add" />
                    </button>
                  </div>
                </>
              )}
            </div>
            <div className="flex-1 overflow-y-auto custom-scrollbar">
              {chat.sessions.length === 0 && (
                <p className="px-3 py-4 text-label-sm text-on-surface-variant text-center">
                  暂无会话，点击 + 新建
                </p>
              )}
              {chat.sessions.map((s) => {
                const isSelected = selectedIds.has(s.id);
                const isActive = s.id === sessionId;
                return (
                  <div
                    key={s.id}
                    className={[
                      "group flex items-center gap-2 px-3 py-2 border-b border-border cursor-pointer hover:bg-surface-container-low",
                      isActive && !batchMode ? "bg-primary-fixed" : "",
                      batchMode && isSelected ? "bg-primary-fixed" : "",
                    ].join(" ")}
                    onClick={() => {
                      if (batchMode) {
                        toggleSelect(s.id);
                      } else {
                        handleSelectSession(s.id);
                      }
                    }}
                  >
                    {batchMode ? (
                      <Icon
                        name={isSelected ? "check_box" : "check_box_outline_blank"}
                        className={[
                          "text-[18px]",
                          isSelected ? "text-primary" : "text-on-surface-variant",
                        ].join(" ")}
                      />
                    ) : (
                      <Icon name="chat_bubble_outline" className="text-[16px] text-on-surface-variant" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-body-sm font-medium truncate">{s.title || "未命名"}</p>
                      <p className="text-label-sm text-on-surface-variant truncate">
                        {s.message_count ?? 0} 条 · {s.space_name || "全局"} · {s.search_strategy}
                      </p>
                    </div>
                    {!batchMode && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteSession(s.id);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 text-on-surface-variant hover:text-error"
                        title="删除"
                      >
                        <Icon name="delete" className="text-[16px]" />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 中间：对话区 */}
        <div className="flex-1 flex flex-col h-full overflow-hidden">
          {/* 顶部配置栏 */}
          <div className="border-b border-border px-4 py-2 flex items-center gap-3 bg-surface flex-wrap">
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="px-2 py-1 text-label-sm border border-border rounded inline-flex items-center gap-1 hover:bg-surface-container-low"
            >
              <Icon name="tune" className="text-[16px]" />
              {showSettings ? "收起" : "展开"}配置
            </button>

            {showSettings && (
              <>
                {/* 模型选择 */}
                <div className="flex items-center gap-1">
                  <label className="text-label-sm text-on-surface-variant">模型</label>
                  <select
                    value={profileId}
                    onChange={(e) => setProfileId(e.target.value)}
                    className="px-2 py-1 text-label-sm border border-border rounded bg-surface max-w-[180px]"
                  >
                    <option value="">默认</option>
                    {chat.profiles.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} {p.is_default ? "★" : ""} · {p.model}
                      </option>
                    ))}
                  </select>
                  {chat.profiles.length === 0 && (
                    <a
                      href="/settings"
                      className="text-label-sm text-primary hover:underline"
                    >
                      去添加
                    </a>
                  )}
                </div>

                {/* 空间选择 */}
                <div className="flex items-center gap-1">
                  <label className="text-label-sm text-on-surface-variant">检索空间</label>
                  <select
                    value={spaceName}
                    onChange={(e) => setSpaceName(e.target.value)}
                    className="px-2 py-1 text-label-sm border border-border rounded bg-surface max-w-[160px]"
                  >
                    <option value="">全局（所有空间）</option>
                    {chat.spaces.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>

                {/* 检索策略 */}
                <div className="flex items-center gap-1">
                  <label className="text-label-sm text-on-surface-variant">策略</label>
                  <select
                    value={strategy}
                    onChange={(e) => setStrategy(e.target.value as Strategy)}
                    className="px-2 py-1 text-label-sm border border-border rounded bg-surface"
                    title={STRATEGY_LABEL[strategy]}
                  >
                    {(Object.keys(STRATEGY_LABEL) as Strategy[]).map((k) => (
                      <option key={k} value={k}>{STRATEGY_LABEL[k]}</option>
                    ))}
                  </select>
                </div>

                {/* top_k */}
                <div className="flex items-center gap-1">
                  <label className="text-label-sm text-on-surface-variant">top_k</label>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={topK}
                    onChange={(e) => setTopK(Math.max(1, Number(e.target.value) || 5))}
                    className="w-14 px-2 py-1 text-label-sm border border-border rounded bg-surface"
                  />
                </div>

                {/* rerank */}
                <label className="flex items-center gap-1 text-label-sm">
                  <input
                    type="checkbox"
                    checked={useRerank}
                    onChange={(e) => setUseRerank(e.target.checked)}
                  />
                  Rerank
                </label>

                {/* 保存到空间 */}
                <div className="flex items-center gap-1 ml-auto">
                  <label className="text-label-sm text-on-surface-variant">问答存入</label>
                  <select
                    value={saveToSpace}
                    onChange={(e) => setSaveToSpace(e.target.value)}
                    className="px-2 py-1 text-label-sm border border-border rounded bg-surface max-w-[160px]"
                  >
                    <option value="">不保存</option>
                    {chat.spaces.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
              </>
            )}
          </div>

          {/* 消息列表 */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto custom-scrollbar px-12 py-8">
            <div className="max-w-[1000px] mx-auto space-y-8">
              {chat.messages.length === 0 && (
                <EmptyState
                  icon="smart_toy"
                  title={sessionId ? "开始对话" : "新建或选择一个会话"}
                  description={
                    sessionId
                      ? "询问任何关于记忆的问题。系统会按所选策略检索并溯源。"
                      : "点击左上角「+」新建一个会话，或在左侧选择历史会话。"
                  }
                />
              )}

              {chat.messages.map((m) => (
                <MessageBubble
                  key={m.id}
                  msg={m}
                  isStreaming={chat.isStreaming}
                  streamingMemories={chat.currentMemories}
                  streamingTrace={chat.currentTrace}
                  streamingThinking={chat.currentThinking}
                  onSave={onSaveMessage}
                  spaces={chat.spaces}
                />
              ))}

              {chat.error && (
                <div className="bg-error/10 border border-error/20 text-error rounded-lg p-3 flex items-center gap-2">
                  <Icon name="error" filled />
                  <span className="text-body-md">{chat.error}</span>
                </div>
              )}
            </div>
          </div>

          {/* 输入框 */}
          <div className="border-t border-border px-panel-padding py-4 bg-surface">
            <form onSubmit={handleSubmit} className="max-w-[1000px] mx-auto flex items-end gap-2">
              <div className="flex-1 relative">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmit(e);
                    }
                  }}
                  placeholder={
                    sessionId
                      ? "输入问题... (Enter 发送, Shift+Enter 换行)"
                      : "按 Enter 自动新建会话并发送..."
                  }
                  rows={1}
                  className="w-full px-4 py-3 bg-surface-container-low border border-border rounded-xl focus:ring-2 focus:ring-primary focus:border-primary outline-none text-body-md resize-none max-h-32"
                  style={{ minHeight: "48px" }}
                />
              </div>
              {chat.isStreaming ? (
                <button
                  type="button"
                  onClick={chat.stop}
                  className="px-4 py-3 bg-error text-on-error rounded-xl font-bold hover:opacity-90 transition-opacity"
                >
                  停止
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!input.trim()}
                  className="px-4 py-3 bg-primary text-on-primary rounded-xl font-bold hover:opacity-90 transition-opacity disabled:opacity-40 flex items-center gap-2"
                >
                  <Icon name="send" className="text-[20px]" />
                  发送
                </button>
              )}
            </form>
            <div className="max-w-[1000px] mx-auto mt-2 flex items-center gap-3 text-label-sm text-on-surface-variant">
              <span>
                模型：
                {chat.profiles.find((p) => p.id === profileId)?.name || "默认"}
              </span>
              <span>·</span>
              <span>空间：{spaceName || "全局"}</span>
              <span>·</span>
              <span>策略：{STRATEGY_LABEL[strategy]}</span>
              {saveToSpace && (
                <>
                  <span>·</span>
                  <span className="text-primary">问答将存入「{saveToSpace}」</span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
