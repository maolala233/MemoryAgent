"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { Pill } from "@/components/shared/Pill";
import { useDocumentImport } from "@/hooks/useDocumentImport";
import type { ImportStep } from "@/hooks/useDocumentImport";

const STEPS: { key: ImportStep; label: string; icon: string }[] = [
  { key: "upload", label: "Upload", icon: "upload_file" },
  { key: "parse", label: "Parse", icon: "text_snippet" },
  { key: "convert", label: "Convert", icon: "transform" },
  { key: "save", label: "Save", icon: "save" },
];

function StepIndicator({
  current,
  progress,
}: {
  current: ImportStep;
  progress: number;
}) {
  const currentIdx = STEPS.findIndex((s) => s.key === current);
  return (
    <div className="flex items-center justify-center gap-2">
      {STEPS.map((step, i) => {
        const done = i < currentIdx || progress === 100;
        const active = i === currentIdx && progress < 100;
        return (
          <div key={step.key} className="flex items-center">
            <div
              className={[
                "flex items-center gap-2 px-3 py-1.5 rounded-full border transition-all",
                done
                  ? "bg-success/10 border-success/30 text-success"
                  : active
                    ? "bg-primary-fixed border-primary text-primary font-bold"
                    : "bg-surface border-border text-on-surface-variant",
              ].join(" ")}
            >
              <Icon
                name={done ? "check_circle" : step.icon}
                filled={done || active}
                className="text-[16px]"
              />
              <span className="text-label-md">{step.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={[
                  "h-px w-8",
                  i < currentIdx ? "bg-success" : "bg-border",
                ].join(" ")}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function ImportPage() {
  const {
    step,
    progress,
    upload,
    parsed,
    converted,
    saved,
    isLoading,
    error,
    uploadFile,
    parse,
    convert,
    save,
    reset,
  } = useDocumentImport();
  const [dragOver, setDragOver] = useState(false);
  const [convertOpts, setConvertOpts] = useState({
    project_id: "",
    memory_type: "note",
    strategy: "section",
  });
  const inputRef = useRef<HTMLInputElement>(null);

  const onFile = useCallback(
    (file: File) => {
      uploadFile(file).then((u) => {
        if (u) parse(u.file_id);
      });
    },
    [uploadFile, parse],
  );

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) onFile(file);
  };

  const onConvert = () => {
    if (!upload) return;
    convert(upload.file_id, {
      project_id: convertOpts.project_id || undefined,
      memory_type: convertOpts.memory_type,
      strategy: convertOpts.strategy,
    });
  };

  const onSave = () => {
    if (!converted || !upload) return;
    save(upload.file_id, converted.memory_files);
  };

  return (
    <AppShell title="Import Document" subtitle="PDF / DOCX / MD → Memory">
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="w-full px-panel-padding py-8 space-y-6">
          {/* Step indicator */}
          <StepIndicator current={step} progress={progress} />

          {/* Progress bar */}
          <div className="h-1 bg-surface-container rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>

          {error && (
            <div className="bg-error/10 border border-error/20 text-error rounded-lg p-3 flex items-center gap-2">
              <Icon name="error" filled />
              <span className="text-body-md">{error}</span>
            </div>
          )}

          {/* Step 1: Upload */}
          {step === "upload" && (
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              className={[
                "bg-surface border-2 border-dashed rounded-xl p-12 text-center transition-all",
                dragOver
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/50",
              ].join(" ")}
            >
              <div className="w-16 h-16 rounded-full bg-primary-fixed flex items-center justify-center mx-auto mb-4">
                <Icon
                  name="upload_file"
                  filled
                  className="text-[32px] text-primary"
                />
              </div>
              <h3 className="text-body-lg font-bold text-on-surface mb-1">
                Drop your file here
              </h3>
              <p className="text-body-md text-on-surface-variant mb-4">
                or click to browse. Supports PDF, DOCX, MD, TXT
              </p>
              <button
                onClick={() => inputRef.current?.click()}
                className="px-6 py-2.5 bg-primary text-on-primary rounded-lg font-bold text-body-md hover:opacity-90 transition-opacity"
              >
                Choose File
              </button>
              <input
                ref={inputRef}
                type="file"
                accept=".pdf,.docx,.md,.txt"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) onFile(f);
                }}
              />
            </div>
          )}

          {/* Step 2: Parse result */}
          {step === "parse" && (
            <div className="bg-surface border border-border rounded-xl p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-body-lg font-bold text-on-surface">
                  Parsed Content
                </h3>
                {upload && (
                  <Pill variant="info" size="md">
                    {upload.filename} · {upload.file_size} bytes
                    {upload.page_count ? ` · ${upload.page_count} pages` : ""}
                  </Pill>
                )}
              </div>
              {isLoading && <Loading label="Parsing document..." />}
              {parsed && (
                <>
                  <p className="text-body-md text-on-surface-variant">
                    Extracted <strong>{parsed.total_chunks}</strong> chunks from the
                    document.
                  </p>
                  <div className="max-h-64 overflow-y-auto custom-scrollbar space-y-2 bg-surface-container-low p-3 rounded-lg">
                    {parsed.chunks.slice(0, 5).map((c) => (
                      <div key={c.index} className="border-l-2 border-primary pl-3">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-label-md font-bold text-primary">
                            #{c.index}
                          </span>
                          {c.section && (
                            <span className="text-label-sm text-on-surface-variant">
                              {c.section}
                            </span>
                          )}
                          <span className="ml-auto text-label-sm text-outline">
                            ~{c.tokens} tokens
                          </span>
                        </div>
                        <p className="text-body-sm text-on-surface line-clamp-3">
                          {c.text}
                        </p>
                      </div>
                    ))}
                    {parsed.chunks.length > 5 && (
                      <p className="text-label-sm text-on-surface-variant text-center pt-2">
                        +{parsed.chunks.length - 5} more chunks...
                      </p>
                    )}
                  </div>
                </>
              )}
            </div>
          )}

          {/* Step 3: Convert options */}
          {step === "convert" && (
            <div className="bg-surface border border-border rounded-xl p-6 space-y-4">
              <h3 className="text-body-lg font-bold text-on-surface">
                Convert to Memory
              </h3>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-label-md text-on-surface-variant mb-1">
                    Project ID
                  </label>
                  <input
                    type="text"
                    value={convertOpts.project_id}
                    onChange={(e) =>
                      setConvertOpts({ ...convertOpts, project_id: e.target.value })
                    }
                    placeholder="optional"
                    className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
                  />
                </div>
                <div>
                  <label className="block text-label-md text-on-surface-variant mb-1">
                    Memory type
                  </label>
                  <select
                    value={convertOpts.memory_type}
                    onChange={(e) =>
                      setConvertOpts({ ...convertOpts, memory_type: e.target.value })
                    }
                    className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
                  >
                    {["note", "decision", "summary", "reference", "log", "spec"].map(
                      (t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ),
                    )}
                  </select>
                </div>
                <div>
                  <label className="block text-label-md text-on-surface-variant mb-1">
                    Strategy
                  </label>
                  <select
                    value={convertOpts.strategy}
                    onChange={(e) =>
                      setConvertOpts({ ...convertOpts, strategy: e.target.value })
                    }
                    className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
                  >
                    <option value="section">Section-aware</option>
                    <option value="size">Fixed-size chunks</option>
                  </select>
                </div>
              </div>
              {isLoading && <Loading label="Converting to memories..." />}
              {converted && (
                <div className="space-y-2">
                  <p className="text-body-md text-on-surface-variant">
                    Generated <strong>{converted.memory_files.length}</strong> memory
                    file(s):
                  </p>
                  {converted.memory_files.map((m, i) => (
                    <div
                      key={i}
                      className="bg-surface-container-low border border-border rounded-lg p-3"
                    >
                      <p className="font-mono text-body-sm text-primary mb-1">
                        {m.rel_path}
                      </p>
                      <p className="text-body-sm text-on-surface-variant line-clamp-2">
                        {(m.frontmatter.summary as string) ||
                          m.content.slice(0, 140) + "..."}
                      </p>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex justify-end gap-2">
                <button
                  onClick={reset}
                  className="px-4 py-2 text-body-md text-on-surface-variant hover:bg-surface-container-low rounded-lg"
                >
                  Restart
                </button>
                {!converted && (
                  <button
                    onClick={onConvert}
                    disabled={isLoading}
                    className="px-4 py-2 bg-primary text-on-primary rounded-lg font-bold text-body-md hover:opacity-90 disabled:opacity-50 flex items-center gap-1"
                  >
                    <Icon name="transform" className="text-[18px]" />
                    Convert
                  </button>
                )}
                {converted && (
                  <button
                    onClick={onSave}
                    disabled={isLoading}
                    className="px-4 py-2 bg-primary text-on-primary rounded-lg font-bold text-body-md hover:opacity-90 disabled:opacity-50 flex items-center gap-1"
                  >
                    <Icon name="save" className="text-[18px]" />
                    Save {converted.memory_files.length} Memories
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Step 4: Save result */}
          {step === "save" && saved && (
            <div className="bg-surface border border-border rounded-xl p-6">
              <div className="text-center mb-4">
                <div className="w-16 h-16 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-4">
                  <Icon
                    name="check_circle"
                    filled
                    className="text-[32px] text-success"
                  />
                </div>
                <h3 className="text-body-lg font-bold text-on-surface mb-1">
                  导入完成
                </h3>
                <p className="text-body-md text-on-surface-variant">
                  已保存 <strong>{saved.saved_count}</strong> 个记忆文件
                  {saved.mandol_synced ? ` · Mandol 同步 ${saved.mandol_synced} 条` : ""}
                </p>
              </div>

              {saved.original_path && (
                <div className="bg-secondary-container rounded-lg p-3 mb-3">
                  <div className="flex items-center gap-2 mb-1">
                    <Icon name="description" className="text-on-secondary-container text-[16px]" />
                    <span className="font-bold text-on-secondary-container text-body-sm">原始文档</span>
                  </div>
                  <p className="font-mono text-label-sm text-on-secondary-container break-all">{saved.original_path}</p>
                </div>
              )}

              {saved.summary_text && (
                <details className="bg-primary-fixed/30 border border-primary/20 rounded-lg mb-3" open>
                  <summary className="p-3 cursor-pointer flex items-center gap-2 font-bold text-on-surface text-body-sm">
                    <Icon name="auto_awesome" className="text-primary text-[16px]" />
                    关键信息摘要（LLM 生成）
                    <span className="text-label-sm text-on-surface-variant ml-auto font-mono">{saved.summary_path}</span>
                  </summary>
                  <div className="px-3 pb-3 text-body-sm text-on-surface leading-relaxed whitespace-pre-wrap max-h-60 overflow-y-auto custom-scrollbar">
                    {saved.summary_text}
                  </div>
                </details>
              )}

              <details className="bg-surface-container-low rounded-lg mb-4">
                <summary className="p-3 cursor-pointer text-body-sm font-bold text-on-surface">所有生成文件 ({saved.paths.length})</summary>
                <div className="px-3 pb-3 text-left max-h-48 overflow-y-auto">
                  {saved.paths.map((p) => (
                    <p key={p} className="font-mono text-label-sm text-primary py-0.5 break-all">{p}</p>
                  ))}
                </div>
              </details>

              <div className="flex justify-center gap-2">
                <button
                  onClick={reset}
                  className="px-4 py-2 border border-border text-on-surface-variant hover:bg-surface-container-low rounded-lg font-medium"
                >
                  再导一份
                </button>
                <Link
                  href="/build"
                  className="px-4 py-2 border border-border text-on-surface rounded-lg font-medium hover:bg-surface-container-low"
                >
                  构建高阶记忆
                </Link>
                <Link
                  href="/memory"
                  className="px-4 py-2 bg-primary text-on-primary rounded-lg font-bold hover:opacity-90"
                >
                  查看记忆库
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
