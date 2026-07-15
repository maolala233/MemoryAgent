"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { Pill } from "@/components/shared/Pill";
import { useDocumentImport } from "@/hooks/useDocumentImport";
import type { ImportStep } from "@/hooks/useDocumentImport";

const STEPS: { key: ImportStep; label: string; icon: string }[] = [
  { key: "upload", label: "上传文件", icon: "upload_file" },
  { key: "parse", label: "解析内容", icon: "text_snippet" },
  { key: "convert", label: "生成记忆", icon: "transform" },
  { key: "save", label: "完成", icon: "save" },
];

// 中文类型映射（数据库里仍是英文枚举，仅 UI 翻译）
const MEMORY_TYPE_LABELS: Record<string, string> = {
  note: "笔记",
  imported_document: "导入文档",
  decision: "决策",
  summary: "摘要",
  reference: "参考",
  log: "日志",
  spec: "规格",
};
const STRATEGY_LABELS: Record<string, string> = {
  section: "按章节切分",
  size: "按固定长度切分",
};

function StepIndicator({
  current,
  progress,
}: {
  current: ImportStep;
  progress: number;
}) {
  const currentIdx = STEPS.findIndex((s) => s.key === current);
  return (
    <div className="flex items-center justify-center gap-2 flex-wrap">
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
    memory_type: "imported_document",
    strategy: "section",
    build_mandol: true,
  });
  const [savingStatus, setSavingStatus] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);

  // 保存阶段持续显示进度文字（避免长时间静默让用户以为卡死）
  useEffect(() => {
    if (step !== "save" || !isLoading) {
      setSavingStatus("");
      return;
    }
    setSavingStatus("正在保存记忆文件…");
    const t1 = setTimeout(() => setSavingStatus("正在调用 LLM 生成摘要（可能需要 1-3 分钟）…"), 1500);
    const t2 = setTimeout(() => setSavingStatus("正在抽取实体与事件…"), 60_000);
    const t3 = setTimeout(() => setSavingStatus("正在构建高阶记忆…"), 120_000);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [step, isLoading]);

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
    save(
      upload.file_id,
      converted.memory_files,
      convertOpts.build_mandol,
      convertOpts.project_id || undefined,
    );
  };

  return (
    <AppShell title="文档导入" subtitle="PDF / DOCX / MD / TXT → 基础记忆">
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
                将文件拖到此处
              </h3>
              <p className="text-body-md text-on-surface-variant mb-1">
                或点击下方按钮选择文件
              </p>
              <p className="text-body-sm text-outline mb-4">
                支持 PDF / DOCX / MD / TXT，单文件最大 50MB
              </p>
              <button
                onClick={() => inputRef.current?.click()}
                className="px-6 py-2.5 bg-primary text-on-primary rounded-lg font-bold text-body-md hover:opacity-90 transition-opacity"
              >
                选择文件
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
              <div className="flex items-center justify-between flex-wrap gap-2">
                <h3 className="text-body-lg font-bold text-on-surface">
                  已解析内容
                </h3>
                {upload && (
                  <Pill variant="info" size="md">
                    {upload.filename} · {(upload.file_size / 1024).toFixed(1)} KB
                    {upload.page_count ? ` · ${upload.page_count} 页` : ""}
                  </Pill>
                )}
              </div>
              {isLoading && <Loading label="正在解析文档…" />}
              {parsed && (
                <>
                  <p className="text-body-md text-on-surface-variant">
                    共抽取 <strong>{parsed.total_chunks}</strong> 个文本片段
                    {parsed.metadata && (parsed.metadata as Record<string, unknown>).title
                      ? `（标题：${String((parsed.metadata as Record<string, unknown>).title)}）`
                      : ""}
                    。
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
                            约 {c.tokens} tokens
                          </span>
                        </div>
                        <p className="text-body-sm text-on-surface line-clamp-3">
                          {c.text}
                        </p>
                      </div>
                    ))}
                    {parsed.chunks.length > 5 && (
                      <p className="text-label-sm text-on-surface-variant text-center pt-2">
                        还有 {parsed.chunks.length - 5} 个片段未显示…
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
                生成基础记忆
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="block text-label-md text-on-surface-variant mb-1">
                    项目 ID（可选）
                  </label>
                  <input
                    type="text"
                    value={convertOpts.project_id}
                    onChange={(e) =>
                      setConvertOpts({ ...convertOpts, project_id: e.target.value })
                    }
                    placeholder="不填则归到默认"
                    className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
                  />
                </div>
                <div>
                  <label className="block text-label-md text-on-surface-variant mb-1">
                    记忆类型
                  </label>
                  <select
                    value={convertOpts.memory_type}
                    onChange={(e) =>
                      setConvertOpts({ ...convertOpts, memory_type: e.target.value })
                    }
                    className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
                  >
                    {["imported_document", "note", "decision", "summary", "reference", "log", "spec"].map(
                      (t) => (
                        <option key={t} value={t}>
                          {MEMORY_TYPE_LABELS[t] ?? t}
                        </option>
                      ),
                    )}
                  </select>
                </div>
                <div>
                  <label className="block text-label-md text-on-surface-variant mb-1">
                    切分策略
                  </label>
                  <select
                    value={convertOpts.strategy}
                    onChange={(e) =>
                      setConvertOpts({ ...convertOpts, strategy: e.target.value })
                    }
                    className="w-full px-3 py-2 bg-surface-container-low border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
                  >
                    {Object.entries(STRATEGY_LABELS).map(([k, v]) => (
                      <option key={k} value={k}>
                        {v}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <label className="flex items-start gap-2 text-body-md text-on-surface-variant cursor-pointer bg-surface-container-low rounded-lg p-3">
                <input
                  type="checkbox"
                  checked={convertOpts.build_mandol}
                  onChange={(e) =>
                    setConvertOpts({ ...convertOpts, build_mandol: e.target.checked })
                  }
                  className="rounded border-border mt-0.5"
                />
                <span>
                  <span className="font-bold text-on-surface">
                    保存时同步触发 Mandol 高阶记忆构建
                  </span>
                  <span className="block text-label-md text-outline mt-0.5">
                    包含 LLM 摘要、实体 / 事件抽取、高阶记忆构建，需 1-3 分钟。
                    关闭后只写基础记忆文件，速度更快。
                  </span>
                </span>
              </label>
              {isLoading && (
                <Loading label="正在生成基础记忆文件…" />
              )}
              {converted && (
                <div className="space-y-2">
                  <p className="text-body-md text-on-surface-variant">
                    已生成 <strong>{converted.memory_files.length}</strong> 个基础记忆文件：
                  </p>
                  {converted.memory_files.map((m, i) => (
                    <div
                      key={m.rel_path || i}
                      className="bg-surface-container-low border border-border rounded-lg p-3"
                    >
                      <p className="font-mono text-body-sm text-primary mb-1 break-all">
                        {m.rel_path}
                      </p>
                      <p className="text-body-sm text-on-surface-variant line-clamp-2">
                        {String(m.frontmatter?.summary ?? "") ||
                          (m.content ? m.content.slice(0, 140) + "..." : "")}
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
                  重新开始
                </button>
                {!converted && (
                  <button
                    onClick={onConvert}
                    disabled={isLoading}
                    className="px-4 py-2 bg-primary text-on-primary rounded-lg font-bold text-body-md hover:opacity-90 disabled:opacity-50 flex items-center gap-1"
                  >
                    <Icon name="transform" className="text-[18px]" />
                    生成基础记忆
                  </button>
                )}
                {converted && (
                  <button
                    onClick={onSave}
                    disabled={isLoading}
                    className="px-4 py-2 bg-primary text-on-primary rounded-lg font-bold text-body-md hover:opacity-90 disabled:opacity-50 flex items-center gap-1"
                  >
                    <Icon name="save" className="text-[18px]" />
                    保存 {converted.memory_files.length} 个记忆
                    {convertOpts.build_mandol && "（含 LLM 构建）"}
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Step 4: Save (long-running with progress text) */}
          {(step === "save" && isLoading) && (
            <div className="bg-surface border border-border rounded-xl p-6 space-y-4">
              <div className="text-center">
                <div className="w-16 h-16 rounded-full bg-primary-fixed flex items-center justify-center mx-auto mb-4">
                  <Icon
                    name="hourglass_top"
                    className="text-[32px] text-primary animate-pulse"
                  />
                </div>
                <h3 className="text-body-lg font-bold text-on-surface mb-1">
                  正在保存记忆…
                </h3>
                <p className="text-body-md text-on-surface-variant">
                  {savingStatus || "请稍候…"}
                </p>
                {!convertOpts.build_mandol && (
                  <p className="text-label-md text-outline mt-1">
                    已跳过 Mandol 高阶记忆构建，仅写入基础记忆文件
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Step 4: Save done */}
          {step === "save" && saved && !isLoading && (
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
                  已保存 <strong>{saved.saved_count}</strong> 个基础记忆文件
                  {saved.mandol_synced
                    ? ` · Mandol 同步 ${saved.mandol_synced} 条`
                    : " · 未触发 Mandol 高阶构建"}
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
                    {saved.summary_path && (
                      <span className="text-label-sm text-on-surface-variant ml-auto font-mono">{saved.summary_path}</span>
                    )}
                  </summary>
                  <div className="px-3 pb-3 text-body-sm text-on-surface leading-relaxed whitespace-pre-wrap max-h-60 overflow-y-auto custom-scrollbar">
                    {saved.summary_text}
                  </div>
                </details>
              )}

              <details className="bg-surface-container-low rounded-lg mb-4">
                <summary className="p-3 cursor-pointer text-body-sm font-bold text-on-surface">
                  所有生成文件（{saved.paths.length}）
                </summary>
                <div className="px-3 pb-3 text-left max-h-48 overflow-y-auto">
                  {saved.paths.map((p) => (
                    <p key={p} className="font-mono text-label-sm text-primary py-0.5 break-all">{p}</p>
                  ))}
                </div>
              </details>

              <div className="flex justify-center gap-2 flex-wrap">
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
