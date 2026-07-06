"use client";

import { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { Pill } from "@/components/shared/Pill";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { MarkdownRenderer } from "@/components/shared/MarkdownRenderer";
import { EmptyState } from "@/components/shared/EmptyState";
import { useMemory } from "@/hooks/useMemory";

function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString();
}

function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

export default function MemoryDetailPage({
  params,
}: {
  params: Promise<{ path: string[] }>;
}) {
  const { path } = use(params);
  const router = useRouter();
  const decodedPath = path.map(encodeURIComponent).join("/");
  // The catch-all gives encoded segments joined by /. We need the decoded path.
  const docPath = path.map((seg) => decodeURIComponent(seg)).join("/");
  const [mode, setMode] = useState<"view" | "edit">("view");
  const [editContent, setEditContent] = useState("");
  const [showDelete, setShowDelete] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const { doc, isLoading, error, getDocument, updateDocument, deleteDocument } =
    useMemory();

  useEffect(() => {
    getDocument(docPath);
  }, [docPath, getDocument]);

  useEffect(() => {
    if (doc) setEditContent(doc.content);
  }, [doc]);

  const onSave = async () => {
    setSaving(true);
    setSaveError(null);
    const updated = await updateDocument(docPath, { content: editContent });
    if (updated) {
      setMode("view");
    } else {
      setSaveError("Failed to save changes");
    }
    setSaving(false);
  };

  const onDelete = async () => {
    const ok = await deleteDocument(docPath);
    if (ok) {
      router.push("/memory");
    }
    setShowDelete(false);
  };

  return (
    <AppShell
      title={doc?.title || docPath}
      subtitle={doc?.track}
      rightSlot={
        doc && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => setMode(mode === "view" ? "edit" : "view")}
              className={[
                "px-3 py-1.5 rounded-lg text-body-md font-medium transition-colors flex items-center gap-1.5",
                mode === "edit"
                  ? "bg-primary text-on-primary"
                  : "text-on-surface-variant hover:bg-surface-container-low",
              ].join(" ")}
            >
              <Icon name={mode === "edit" ? "visibility" : "edit"} className="text-[18px]" />
              {mode === "edit" ? "Preview" : "Edit"}
            </button>
            <button
              onClick={() => setShowDelete(true)}
              className="p-1.5 rounded-lg text-on-surface-variant hover:bg-error/10 hover:text-error transition-colors"
              title="Delete"
            >
              <Icon name="delete" className="text-[20px]" />
            </button>
          </div>
        )
      }
    >
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="max-w-max-content-width mx-auto px-panel-padding py-8">
          {isLoading && !doc && <Loading size="lg" label="Loading memory..." />}

          {error && !doc && (
            <EmptyState
              icon="error"
              title="Memory not found"
              description={error}
              action={
                <Link href="/memory" className="text-primary hover:underline">
                  ← Back to vault
                </Link>
              }
            />
          )}

          {saveError && (
            <div className="bg-error/10 border border-error/20 text-error rounded-lg p-3 mb-4">
              {saveError}
            </div>
          )}

          {doc && (
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
              {/* Main content */}
              <div className="min-w-0">
                {/* Header card */}
                <div className="bg-surface border border-border rounded-xl p-5 mb-4">
                  <div className="flex items-start gap-3 mb-3">
                    <Icon
                      name="description"
                      filled
                      className="text-primary text-[24px] mt-0.5"
                    />
                    <div className="flex-1 min-w-0">
                      <h1 className="text-headline-md font-headline-md font-bold text-on-surface">
                        {doc.title || doc.rel_path}
                      </h1>
                      <p className="text-label-sm text-outline font-mono mt-1">
                        {doc.rel_path}
                      </p>
                    </div>
                  </div>
                  {doc.summary && (
                    <p className="text-body-md text-on-surface-variant leading-relaxed">
                      {doc.summary}
                    </p>
                  )}
                  <div className="flex flex-wrap items-center gap-1.5 mt-3">
                    <Pill variant="info" size="sm">
                      {doc.track}
                    </Pill>
                    <Pill size="sm">{doc.memory_type}</Pill>
                    <Pill
                      variant={doc.status === "verified" ? "success" : "default"}
                      size="sm"
                    >
                      {doc.status}
                    </Pill>
                    {doc.keywords.map((k) => (
                      <Pill key={k} variant="primary" size="sm">
                        #{k}
                      </Pill>
                    ))}
                  </div>
                </div>

                {/* Content / Editor */}
                <div className="bg-surface border border-border rounded-xl p-6">
                  {mode === "view" ? (
                    doc.content ? (
                      <MarkdownRenderer content={doc.content} />
                    ) : (
                      <p className="text-body-md text-on-surface-variant italic">
                        No content.
                      </p>
                    )
                  ) : (
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-body-md font-bold text-on-surface">
                          Edit content
                        </h3>
                        <div className="flex gap-2">
                          <button
                            onClick={() => {
                              setEditContent(doc.content);
                              setMode("view");
                            }}
                            className="px-3 py-1.5 text-body-sm font-medium text-on-surface-variant hover:bg-surface-container-low rounded-lg"
                          >
                            Cancel
                          </button>
                          <button
                            onClick={onSave}
                            disabled={saving}
                            className="px-4 py-1.5 bg-primary text-on-primary rounded-lg text-body-sm font-bold hover:opacity-90 disabled:opacity-50 flex items-center gap-1"
                          >
                            <Icon name="save" className="text-[16px]" />
                            Save
                          </button>
                        </div>
                      </div>
                      <textarea
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                        rows={24}
                        className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg font-mono text-body-md focus:ring-2 focus:ring-primary outline-none resize-y"
                      />
                    </div>
                  )}
                </div>
              </div>

              {/* Metadata sidebar */}
              <aside className="space-y-4">
                <div className="bg-surface border border-border rounded-xl p-4">
                  <h3 className="text-body-md font-bold text-on-surface mb-3 flex items-center gap-2">
                    <Icon name="info" className="text-[18px] text-on-surface-variant" />
                    Metadata
                  </h3>
                  <dl className="space-y-2 text-body-sm">
                    <div>
                      <dt className="text-on-surface-variant">Track</dt>
                      <dd className="font-medium text-on-surface">{doc.track}</dd>
                    </div>
                    <div>
                      <dt className="text-on-surface-variant">Type</dt>
                      <dd className="font-medium text-on-surface">{doc.memory_type}</dd>
                    </div>
                    <div>
                      <dt className="text-on-surface-variant">Status</dt>
                      <dd className="font-medium text-on-surface">{doc.status}</dd>
                    </div>
                    {doc.project_id && (
                      <div>
                        <dt className="text-on-surface-variant">Project</dt>
                        <dd className="font-mono text-on-surface">{doc.project_id}</dd>
                      </div>
                    )}
                    <div>
                      <dt className="text-on-surface-variant">Size</dt>
                      <dd className="font-medium text-on-surface">
                        {formatBytes(doc.size_bytes)}
                      </dd>
                    </div>
                  </dl>
                </div>

                <div className="bg-surface border border-border rounded-xl p-4">
                  <h3 className="text-body-md font-bold text-on-surface mb-3 flex items-center gap-2">
                    <Icon name="schedule" className="text-[18px] text-on-surface-variant" />
                    Timeline
                  </h3>
                  <dl className="space-y-2 text-body-sm">
                    <div>
                      <dt className="text-on-surface-variant">Created</dt>
                      <dd className="font-medium text-on-surface">
                        {formatDate(doc.created_at)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-on-surface-variant">Updated</dt>
                      <dd className="font-medium text-on-surface">
                        {formatDate(doc.updated_at)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-on-surface-variant">Indexed</dt>
                      <dd className="font-medium text-on-surface">
                        {formatDate(doc.indexed_at)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-on-surface-variant">Verified</dt>
                      <dd className="font-medium text-on-surface">
                        {formatDate(doc.verified_at)}
                      </dd>
                    </div>
                  </dl>
                </div>

                {doc.open_loops.length > 0 && (
                  <div className="bg-surface border border-border rounded-xl p-4">
                    <h3 className="text-body-md font-bold text-on-surface mb-3 flex items-center gap-2">
                      <Icon name="pending_actions" className="text-[18px] text-warning" />
                      Open Loops ({doc.open_loops.length})
                    </h3>
                    <ul className="space-y-2">
                      {doc.open_loops.map((loop, i) => (
                        <li
                          key={i}
                          className="text-body-sm border-l-2 border-warning pl-2"
                        >
                          <div className="flex items-center gap-2">
                            <Pill variant="warning" size="sm">
                              {loop.kind}
                            </Pill>
                            {loop.priority && (
                              <span className="text-label-sm text-outline">
                                {loop.priority}
                              </span>
                            )}
                          </div>
                          <p className="text-on-surface mt-1">{loop.item}</p>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Frontmatter raw */}
                <details className="bg-surface border border-border rounded-xl p-4">
                  <summary className="text-body-md font-bold text-on-surface cursor-pointer flex items-center gap-2">
                    <Icon name="code" className="text-[18px] text-on-surface-variant" />
                    Frontmatter
                  </summary>
                  <pre className="mt-3 text-label-md font-mono text-on-surface-variant bg-surface-container-low p-3 rounded overflow-x-auto">
{JSON.stringify(doc.frontmatter, null, 2)}
                  </pre>
                </details>
              </aside>
            </div>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={showDelete}
        title="Delete memory?"
        message={`This will permanently remove "${doc?.title || docPath}" from your vault.`}
        confirmLabel="Delete"
        variant="danger"
        onConfirm={onDelete}
        onCancel={() => setShowDelete(false)}
      />
    </AppShell>
  );
}
