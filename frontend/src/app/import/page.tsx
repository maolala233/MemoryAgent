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
  { key: "convert", label: "切片", icon: "transform" },
  { key: "save", label: "生成记忆", icon: "auto_awesome" },
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

function StatBox({
  label,
  value,
  icon,
  color = "primary",
}: {
  label: string;
  value: number | string;
  icon: string;
  color?: "primary" | "info" | "success";
}) {
  const colorClass = {
    primary: "bg-primary-fixed text-primary",
    info: "bg-info/10 text-info",
    success: "bg-success/10 text-success",
  }[color];
  return (
    <div className="bg-surface-container-low border border-border rounded-lg p-3 flex items-center gap-3">
      <div className={["w-10 h-10 rounded-full flex items-center justify-center shrink-0", colorClass].join(" ")}>
        <Icon name={icon} className="text-[20px]" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-label-md text-on-surface-variant truncate">{label}</p>
        <p className="text-body-lg font-bold text-on-surface">{value}</p>
      </div>
    </div>
  );
}

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
    buildStatus,
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
  const [buildLog, setBuildLog] = useState<
    { ts: number; level: "info" | "ok" | "err"; text: string }[]
  >([]);
  const [toast, setToast] = useState<{
    type: "ok" | "err";
    title: string;
    detail?: string;
  } | null>(null);
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

  // 把后端实时构建状态写进日志 + toast
  useEffect(() => {
    if (!buildStatus) return;
    setBuildLog((prev) => {
      const last = prev[prev.length - 1];
      const text = buildStatus.message || (buildStatus.status === "running" ? "正在构建..." : "");
      if (!text) return prev;
      if (last && last.text === text) return prev; // 去重
      const level: "info" | "ok" | "err" =
        buildStatus.status === "completed"
          ? "ok"
          : buildStatus.status === "failed"
            ? "err"
            : "info";
      const next = [
        ...prev,
        { ts: Date.now(), level, text },
      ];
      // 最多保留 50 条
      return next.slice(-50);
    });
  }, [buildStatus]);

  // 构建结束 -> 弹提醒
  useEffect(() => {
    if (!buildStatus) return;
    if (buildStatus.status === "completed") {
      setToast({
        type: "ok",
        title: "高阶记忆构建完成",
        detail: `耗时 ${buildStatus.elapsed_seconds}s, 可前往「记忆库」开始对话。`,
      });
    } else if (buildStatus.status === "failed") {
      setToast({
        type: "err",
        title: "高阶记忆构建失败",
        detail: buildStatus.message,
      });
    }
  }, [buildStatus?.status]);

  // convert 完成后, 如果开了 build_mandol, 自动保存
  const autoSaveTriggered = useRef(false);
  useEffect(() => {
    if (
      step === "save" &&
      converted &&
      upload &&
      !saved &&
      convertOpts.build_mandol &&
      !isLoading &&
      !autoSaveTriggered.current
    ) {
      autoSaveTriggered.current = true;
      setBuildLog([{ ts: Date.now(), level: "info", text: "已触发保存, 后台开始构建..." }]);
      save(
        upload.file_id,
        converted.memory_files,
        true,
        convertOpts.project_id || undefined,
      );
    }
    if (step === "upload") {
      autoSaveTriggered.current = false;
    }
  }, [step, converted, upload, saved, isLoading, convertOpts.build_mandol, convertOpts.project_id, save]);

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
    <AppShell title="文档导入" subtitle="PDF / DOCX / MD / TXT → 记忆">
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

          {/* Step 4: 生成记忆 (save + build 合在一起, 实时显示进度+日志+抽取结果) */}
          {step === "save" && (
            <div className="bg-surface border border-border rounded-xl p-6 space-y-4">
              {/* ---- 顶部状态行 ---- */}
              <div className="flex items-center gap-3 flex-wrap">
                <div
                  className={[
                    "w-12 h-12 rounded-full flex items-center justify-center",
                    isLoading || buildStatus?.status === "running"
                      ? "bg-primary-fixed"
                      : buildStatus?.status === "completed"
                        ? "bg-success/10"
                        : buildStatus?.status === "failed"
                          ? "bg-error/10"
                          : "bg-surface-container-low",
                  ].join(" ")}
                >
                  <Icon
                    name={
                      isLoading || buildStatus?.status === "running"
                        ? "hourglass_top"
                        : buildStatus?.status === "completed"
                          ? "check_circle"
                          : buildStatus?.status === "failed"
                            ? "error"
                            : "auto_awesome"
                    }
                    filled
                    className={[
                      "text-[28px]",
                      isLoading || buildStatus?.status === "running"
                        ? "text-primary animate-pulse"
                        : buildStatus?.status === "completed"
                          ? "text-success"
                          : buildStatus?.status === "failed"
                            ? "text-error"
                            : "text-on-surface-variant",
                    ].join(" ")}
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-body-lg font-bold text-on-surface">
                    {buildStatus?.status === "completed"
                      ? "生成记忆完成"
                      : buildStatus?.status === "failed"
                        ? "生成记忆失败"
                        : isLoading
                          ? "正在保存并构建高阶记忆…"
                          : saved
                            ? "已生成基础记忆"
                            : "准备生成记忆"}
                  </h3>
                  <p className="text-body-md text-on-surface-variant break-all">
                    {buildStatus?.message || savingStatus || "请稍候…"}
                  </p>
                  {buildStatus && buildStatus.elapsed_seconds > 0 && (
                    <p className="text-label-sm text-outline mt-0.5">
                      已运行 {buildStatus.elapsed_seconds}s
                      {buildStatus.status === "running"}
                    </p>
                  )}
                </div>
                {buildStatus && buildStatus.status !== "running" && (
                  <button
                    onClick={reset}
                    className="px-3 py-1.5 text-body-sm border border-border text-on-surface-variant hover:bg-surface-container-low rounded-lg"
                  >
                    再导一份
                  </button>
                )}
              </div>

              {/* ---- 保存结果摘要 ---- */}
              {saved && !isLoading && (
                <div className="text-body-md text-on-surface-variant">
                  已保存 <strong className="text-on-surface">{saved.saved_count}</strong> 个基础记忆文件
                  {saved.mandol_synced
                    ? ` · Mandol 同步 ${saved.mandol_synced} 条`
                    : " · 未触发 Mandol 高阶构建"}
                </div>
              )}

              {/* ---- 抽取结果 (构建完成后展示) ---- */}
              {buildStatus?.result?.extraction && buildStatus.status === "completed" && (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <StatBox
                      label="入库单元"
                      value={buildStatus.result.extraction.total_units}
                      icon="layers"
                      color="primary"
                    />
                    <StatBox
                      label="实体总数"
                      value={buildStatus.result.extraction.entity_count}
                      icon="person"
                      color="info"
                    />
                    <StatBox
                      label="事件总数"
                      value={buildStatus.result.extraction.event_count}
                      icon="event"
                      color="info"
                    />
                    <StatBox
                      label="图谱节点/边"
                      value={`${buildStatus.result.neo4j_sync?.nodes ?? 0} / ${buildStatus.result.neo4j_sync?.edges ?? 0}`}
                      icon="hub"
                      color="primary"
                    />
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <StatBox
                      label="本次抽取实体"
                      value={buildStatus.result.extraction.entities_extracted}
                      icon="science"
                      color="primary"
                    />
                    <StatBox
                      label="本次新增实体"
                      value={buildStatus.result.extraction.entities_added}
                      icon="person_add"
                      color="success"
                    />
                    <StatBox
                      label="实体重复未入库"
                      value={buildStatus.result.extraction.entities_deduped}
                      icon="content_copy"
                      color="primary"
                    />
                    <StatBox
                      label="实体重复率"
                      value={`${buildStatus.result.extraction.entities_extracted
                          ? Math.round(
                            (buildStatus.result.extraction.entities_deduped /
                              buildStatus.result.extraction.entities_extracted) *
                            100,
                          )
                          : 0
                        }%`}
                      icon="percent"
                      color="primary"
                    />
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <StatBox
                      label="本次抽取事件"
                      value={buildStatus.result.extraction.events_extracted}
                      icon="science"
                      color="primary"
                    />
                    <StatBox
                      label="本次新增事件"
                      value={buildStatus.result.extraction.events_added}
                      icon="event_available"
                      color="success"
                    />
                    <StatBox
                      label="事件重复未入库"
                      value={buildStatus.result.extraction.events_deduped}
                      icon="content_copy"
                      color="primary"
                    />
                    <StatBox
                      label="事件重复率"
                      value={`${buildStatus.result.extraction.events_extracted
                          ? Math.round(
                            (buildStatus.result.extraction.events_deduped /
                              buildStatus.result.extraction.events_extracted) *
                            100,
                          )
                          : 0
                        }%`}
                      icon="percent"
                      color="primary"
                    />
                  </div>
                </>
              )}

              {/* ---- Neo4j 同步结果 ---- */}
              {buildStatus?.result?.neo4j_sync && buildStatus.status === "completed" && (
                <div className="bg-surface-container-low rounded-lg p-3 text-label-md text-on-surface-variant flex items-center gap-3 flex-wrap">
                  <Icon name="hub" className="text-on-surface-variant text-[16px]" />
                  <span>
                    Neo4j 图谱同步: <strong className="text-on-surface">{buildStatus.result.neo4j_sync.nodes ?? 0}</strong> 节点 / <strong className="text-on-surface">{buildStatus.result.neo4j_sync.edges ?? 0}</strong> 关系
                  </span>
                </div>
              )}

              {/* ---- 原始文档 / 摘要 ---- */}
              {saved?.original_path && (
                <div className="bg-secondary-container rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <Icon name="description" className="text-on-secondary-container text-[16px]" />
                    <span className="font-bold text-on-secondary-container text-body-sm">原始文档</span>
                  </div>
                  <p className="font-mono text-label-sm text-on-secondary-container break-all">{saved.original_path}</p>
                </div>
              )}

              {saved?.summary_text && (
                <details className="bg-primary-fixed/30 border border-primary/20 rounded-lg" open>
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

              {/* ---- 实时日志 ---- */}
              {buildLog.length > 0 && (
                <details open className="bg-surface-container-low rounded-lg">
                  <summary className="p-3 cursor-pointer text-body-sm font-bold text-on-surface flex items-center gap-2">
                    <Icon name="terminal" className="text-on-surface-variant text-[16px]" />
                    实时日志（{buildLog.length}）
                  </summary>
                  <div className="px-3 pb-3 max-h-56 overflow-y-auto custom-scrollbar font-mono text-label-sm space-y-1">
                    {buildLog.map((e, i) => (
                      <div
                        key={i}
                        className={[
                          "flex items-start gap-2",
                          e.level === "ok"
                            ? "text-success"
                            : e.level === "err"
                              ? "text-error"
                              : "text-on-surface-variant",
                        ].join(" ")}
                      >
                        <span className="text-outline shrink-0">
                          {new Date(e.ts).toLocaleTimeString("zh-CN", { hour12: false })}
                        </span>
                        <span className="shrink-0">
                          {e.level === "ok" ? "✓" : e.level === "err" ? "✗" : "·"}
                        </span>
                        <span className="break-all">{e.text}</span>
                      </div>
                    ))}
                  </div>
                </details>
              )}

              {!isLoading && buildStatus?.status === "running" && (
                <p className="text-label-sm text-outline text-center">
                  本页可保持不动；构建完会有弹窗提醒。
                </p>
              )}
            </div>
          )}

          {/* Toast */}
          {toast && (
            <div
              role="alert"
              className={[
                "fixed bottom-6 right-6 z-50 max-w-sm rounded-xl shadow-2xl border p-4 flex items-start gap-3 animate-[slideIn_.3s_ease-out]",
                toast.type === "ok"
                  ? "bg-success/10 border-success/30"
                  : "bg-error/10 border-error/30",
              ].join(" ")}
            >
              <Icon
                name={toast.type === "ok" ? "check_circle" : "error"}
                filled
                className={[
                  "text-[24px] shrink-0",
                  toast.type === "ok" ? "text-success" : "text-error",
                ].join(" ")}
              />
              <div className="flex-1 min-w-0">
                <p
                  className={[
                    "font-bold text-body-md",
                    toast.type === "ok" ? "text-success" : "text-error",
                  ].join(" ")}
                >
                  {toast.title}
                </p>
                {toast.detail && (
                  <p className="text-body-sm text-on-surface mt-0.5 break-all">
                    {toast.detail}
                  </p>
                )}
                <div className="flex gap-3 mt-2">
                  {toast.type === "ok" && (
                    <Link
                      href="/memory"
                      onClick={() => setToast(null)}
                      className="text-label-md font-bold text-primary hover:underline"
                    >
                      去记忆库 →
                    </Link>
                  )}
                  <button
                    onClick={() => setToast(null)}
                    className="text-label-md text-on-surface-variant hover:underline"
                  >
                    关闭
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 完成后: 文件清单 + 快捷按钮 (save+build 视图已合并) */}
          {step === "save" && saved && !isLoading && buildStatus?.status === "completed" && (
            <div className="bg-surface border border-border rounded-xl p-6 space-y-3">
              <details className="bg-surface-container-low rounded-lg">
                <summary className="p-3 cursor-pointer text-body-sm font-bold text-on-surface">
                  所有生成文件（{saved.paths.length}）
                </summary>
                <div className="px-3 pb-3 max-h-48 overflow-y-auto">
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
