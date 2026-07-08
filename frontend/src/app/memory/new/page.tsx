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
      setError("Path is required (e.g. project/foo.md)");
      return;
    }
    if (!content.trim()) {
      setError("Content cannot be empty");
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
        setError("Failed to create memory");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell title="New Memory" subtitle="Create a new entry">
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
            <h3 className="text-body-lg font-bold text-on-surface">Metadata</h3>

            <div>
              <label className="block text-label-md text-on-surface-variant mb-1">
                Path <span className="text-error">*</span>
              </label>
              <input
                type="text"
                value={relPath}
                onChange={(e) => setRelPath(e.target.value)}
                placeholder="project/my-new-memory.md"
                className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg font-mono text-body-md focus:ring-2 focus:ring-primary outline-none"
              />
              <p className="text-label-sm text-outline mt-1">
                Relative path within the vault. Auto-appends .md if missing.
              </p>
            </div>

            <div>
              <label className="block text-label-md text-on-surface-variant mb-1">
                Title
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="My New Memory"
                className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-label-md text-on-surface-variant mb-1">
                  Track
                </label>
                <select
                  value={track}
                  onChange={(e) => setTrack(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
                >
                  {TRACKS.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-label-md text-on-surface-variant mb-1">
                  Type
                </label>
                <select
                  value={memoryType}
                  onChange={(e) => setMemoryType(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
                >
                  {TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-label-md text-on-surface-variant mb-1">
                  Status
                </label>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
                >
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-label-md text-on-surface-variant mb-1">
                Summary
              </label>
              <input
                type="text"
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                placeholder="One-line description"
                className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
              />
            </div>

            <div>
              <label className="block text-label-md text-on-surface-variant mb-1">
                Keywords (comma-separated)
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
              <h3 className="text-body-lg font-bold text-on-surface">Content</h3>
              <span className="text-label-sm text-outline">
                Markdown supported
              </span>
            </div>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="# Heading&#10;&#10;Write your memory content in Markdown..."
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
              Cancel
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
              Save Memory
            </button>
          </div>
        </form>
      </div>
    </AppShell>
  );
}
