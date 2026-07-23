"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { useMemory } from "@/hooks/useMemory";
import { api, ApiError } from "@/services/api";

const TRACKS = ["project", "learning", "research", "reference", "personal"];
const TYPES = ["note", "decision", "summary", "reference", "log", "spec", "issue"];
const STATUSES = ["draft", "active", "verified", "archived"];

// 友好显示名（数据库里仍是英文，仅在 UI 翻译），与 memory 列表/import 页面保持一致
const STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  active: "活跃",
  verified: "已验证",
  archived: "已归档",
};
const TYPE_LABELS: Record<string, string> = {
  note: "笔记",
  decision: "决策",
  summary: "摘要",
  reference: "参考",
  log: "日志",
  spec: "规格",
  issue: "问题",
};
const TRACK_LABELS: Record<string, string> = {
  project: "项目",
  learning: "学习",
  research: "研究",
  reference: "参考",
  personal: "个人",
};

export default function NewMemoryPage() {
  const router = useRouter();
  const { createDocument } = useMemory();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [relPath, setRelPath] = useState("");
  const [title, setTitle] = useState("");
  const [track, setTrack] = useState("project");
  const [memoryType, setMemoryType] = useState("note");
  const [status, setStatus] = useState("draft");
  const [summary, setSummary] = useState("");
  const [keywords, setKeywords] = useState("");
  const [content, setContent] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!relPath.trim()) {
      setError("请填写路径（例如 project/foo.md）");
      return;
    }
    if (!content.trim()) {
      setError("内容不能为空");
      return;
    }

    setSaving(true);
    try {
      // Build markdown with frontmatter so it's a proper memory doc.
      const kws = keywords
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean);
      const fm: Record<string, unknown> = {
        title: title || relPath.replace(/\.md$/i, ""),
        memory_type: memoryType,
        track,
        status,
        summary,
        keywords: kws,
        created_at: new Date().toISOString(),
      };
      // Use the create endpoint which accepts structured fields.
      const created = await createDocument({
        rel_path: relPath.endsWith(".md") ? relPath : `${relPath}.md`,
        content,
        memory_type: memoryType,
        track,
        summary,
        keywords: kws,
      });
      if (created) {
        router.push(`/memory/${encodeURIComponent(created.rel_path)}`);
      } else {
        setError("创建记忆失败");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell title="新建记忆" subtitle="创建一条新记忆">
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <form
          onSubmit={onSubmit}
          className="w-full px-panel-padding py-8 space-y-6"
        >
          {error && (
            <div className="bg-error/10 border border-error/20 text-error rounded-lg p-3 flex items-center gap-2">
              <Icon name="error" filled />
              <span className="text-body-md">{error}</span>
            </div>
          )}

          <div className="bg-surface border border-border rounded-xl p-6 space-y-4">
            <h3 className="text-body-lg font-bold text-on-surface">元数据</h3>

            <div>
              <label className="block text-label-md text-on-surface-variant mb-1">
                路径 <span className="text-error">*</span>
              </label>
              <input
                type="text"
                value={relPath}
                onChange={(e) => setRelPath(e.target.value)}
                placeholder="project/my-new-memory.md"
                className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg font-mono text-body-md focus:ring-2 focus:ring-primary outline-none"
              />
              <p className="text-label-sm text-outline mt-1">
                vault 内的相对路径，缺少后缀时自动补 .md
              </p>
            </div>

            <div>
              <label className="block text-label-md text-on-surface-variant mb-1">
                标题
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="我的新记忆"
                className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-label-md text-on-surface-variant mb-1">
                  轨道
                </label>
                <select
                  value={track}
                  onChange={(e) => setTrack(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
                >
                  {TRACKS.map((t) => (
                    <option key={t} value={t}>
                      {TRACK_LABELS[t] ?? t}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-label-md text-on-surface-variant mb-1">
                  类型
                </label>
                <select
                  value={memoryType}
                  onChange={(e) => setMemoryType(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
                >
                  {TYPES.map((t) => (
                    <option key={t} value={t}>
                      {TYPE_LABELS[t] ?? t}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-label-md text-on-surface-variant mb-1">
                  状态
                </label>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
                >
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {STATUS_LABELS[s] ?? s}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-label-md text-on-surface-variant mb-1">
                摘要
              </label>
              <input
                type="text"
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                placeholder="一句话描述"
                className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
              />
            </div>

            <div>
              <label className="block text-label-md text-on-surface-variant mb-1">
                关键词（用逗号分隔）
              </label>
              <input
                type="text"
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="api, design, decision"
                className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg font-mono text-body-md focus:ring-2 focus:ring-primary outline-none"
              />
            </div>
          </div>

          <div className="bg-surface border border-border rounded-xl p-6 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-body-lg font-bold text-on-surface">内容</h3>
              <span className="text-label-sm text-outline">
                支持 Markdown 语法
              </span>
            </div>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="# 标题&#10;&#10;用 Markdown 写下你的记忆内容..."
              rows={16}
              className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg font-mono text-body-md focus:ring-2 focus:ring-primary outline-none resize-y"
            />
          </div>

          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={() => router.back()}
              className="px-4 py-2 text-body-md font-medium text-on-surface-variant hover:bg-surface-container-low rounded-lg transition-colors"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-6 py-2 bg-primary text-on-primary rounded-lg font-bold text-body-md hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
            >
              {saving ? (
                <Loading size="sm" />
              ) : (
                <Icon name="save" className="text-[18px]" />
              )}
              保存记忆
            </button>
          </div>
        </form>
      </div>
    </AppShell>
  );
}
