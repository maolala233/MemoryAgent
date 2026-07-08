"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { api, ApiError } from "@/services/api";

interface MandolConfig {
  enabled: boolean;
  storage_dir: string;
  enable_persistence: boolean;
  auto_save_interval: number;
  llm: {
    model: string;
    base_url: string;
    api_key: string;
    temperature: number;
    max_tokens: number;
  };
  embedder: {
    model: string;
    device: string;
    dimension: number;
    use_remote: boolean;
    remote_base_url: string;
    remote_api_path: string;
    remote_timeout: number;
  };
  reranker: {
    model: string;
    device: string;
    use_remote: boolean;
    remote_base_url: string;
    remote_api_path: string;
    remote_timeout: number;
  };
  system: {
    chunk_max_tokens: number;
    session_time_gap_seconds: number;
    session_check_interval: number;
    session_max_pending: number;
    similarity_top_k: number;
    similarity_threshold: number;
    similarity_recent_window: number;
    bfs_expansion_per_seed: number;
    bfs_expansion_hops: number;
    max_context_units: number;
    max_entities_per_llm: number;
    max_events_per_llm: number;
    promote_threshold: number;
    use_unified_pipeline: boolean;
  };
}

export default function SettingsPage() {
  const [config, setConfig] = useState<MandolConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [activeTab, setActiveTab] = useState<"llm" | "embedder" | "reranker" | "system">("llm");

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setIsLoading(true);
    try {
      const data = await api.get<{ mandol: MandolConfig; is_ready: boolean }>("settings/config");
      setConfig(data.mandol);
    } catch (err) {
      setMessage(`加载配置失败: ${err instanceof ApiError ? err.detail : "未知错误"}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    if (!config) return;
    setIsSaving(true);
    setMessage("");
    try {
      const data = await api.post<{ status: string; message: string }>("settings/config", { mandol: config });
      setMessage(data.message);
    } catch (err) {
      setMessage(`保存失败: ${err instanceof ApiError ? err.detail : "未知错误"}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleReconfigure = async () => {
    setIsSaving(true);
    setMessage("");
    try {
      const data = await api.post<{ status: string; message: string }>("settings/reconfigure");
      setMessage(data.message);
    } catch (err) {
      setMessage(`重新配置失败: ${err instanceof ApiError ? err.detail : "未知错误"}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleTest = async () => {
    setMessage("");
    try {
      const data = await api.get<{ llm: boolean; embedder: boolean; reranker: boolean; error?: string }>("settings/providers/test");
      setMessage(`LLM: ${data.llm ? "✓" : "✗"} | Embedder: ${data.embedder ? "✓" : "✗"} | Reranker: ${data.reranker ? "✓" : "✗"}`);
    } catch (err) {
      setMessage(`测试失败: ${err instanceof ApiError ? err.detail : "未知错误"}`);
    }
  };

  const updateField = (path: string, value: any) => {
    if (!config) return;
    const keys = path.split(".");
    const newConfig = JSON.parse(JSON.stringify(config));
    let obj = newConfig;
    for (let i = 0; i < keys.length - 1; i++) {
      obj = obj[keys[i]];
    }
    obj[keys[keys.length - 1]] = value;
    setConfig(newConfig);
  };

  if (isLoading) {
    return (
      <AppShell title="系统设置" subtitle="模型与系统参数配置">
        <div className="flex-1 flex items-center justify-center">
          <Loading size="lg" label="加载配置中..." />
        </div>
      </AppShell>
    );
  }

  if (!config) {
    return (
      <AppShell title="系统设置" subtitle="模型与系统参数配置">
        <div className="flex-1 flex items-center justify-center">
          <p className="text-on-surface-variant">{message || "配置加载失败"}</p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell title="系统设置" subtitle="模型与系统参数配置">
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="w-full px-panel-padding py-8 space-y-6">
          {/* 基础开关 */}
          <section className="bg-surface border border-border rounded-xl p-5">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-body-lg font-bold text-on-surface">Mandol 记忆引擎</h3>
                <p className="text-body-sm text-on-surface-variant mt-1">
                  启用后可使用 Mandol 的分层记忆、多视图检索与图谱能力
                </p>
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.enabled}
                  onChange={(e) => updateField("enabled", e.target.checked)}
                  className="w-5 h-5 accent-primary"
                />
                <span className="text-body-md font-medium">{config.enabled ? "已启用" : "已禁用"}</span>
              </label>
            </div>
          </section>

          {/* 标签切换 */}
          <div className="flex items-center gap-2 border-b border-border">
            {[
              { key: "llm" as const, label: "LLM 大语言模型", icon: "smart_toy" },
              { key: "embedder" as const, label: "Embedding 嵌入模型", icon: "data_object" },
              { key: "reranker" as const, label: "Reranker 重排序模型", icon: "sort" },
              { key: "system" as const, label: "系统参数", icon: "tune" },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={[
                  "flex items-center gap-2 px-4 py-2 text-body-md font-medium transition-colors border-b-2",
                  activeTab === tab.key
                    ? "border-primary text-primary"
                    : "border-transparent text-on-surface-variant hover:text-on-surface",
                ].join(" ")}
              >
                <Icon name={tab.icon} className="text-[18px]" />
                {tab.label}
              </button>
            ))}
          </div>

          {/* LLM 配置 */}
          {activeTab === "llm" && (
            <section className="bg-surface border border-border rounded-xl p-5 space-y-4">
              <h3 className="text-body-lg font-bold text-on-surface">LLM 大语言模型配置</h3>
              <p className="text-body-sm text-on-surface-variant">
                支持 OpenAI 兼容接口（Ollama、vLLM、云服务模型接口等）
              </p>
              <Field label="模型名称" value={config.llm.model} onChange={(v) => updateField("llm.model", v)} placeholder="gpt-4o-mini" />
              <Field label="API Base URL" value={config.llm.base_url} onChange={(v) => updateField("llm.base_url", v)} placeholder="https://api.openai.com/v1 或 http://localhost:11434/v1" />
              <Field label="API Key" value={config.llm.api_key} onChange={(v) => updateField("llm.api_key", v)} placeholder="sk-...（留空使用环境变量）" type="password" />
              <div className="grid grid-cols-2 gap-4">
                <NumberField label="Temperature" value={config.llm.temperature} onChange={(v) => updateField("llm.temperature", v)} step={0.1} />
                <NumberField label="Max Tokens" value={config.llm.max_tokens} onChange={(v) => updateField("llm.max_tokens", v)} />
              </div>
            </section>
          )}

          {/* Embedder 配置 */}
          {activeTab === "embedder" && (
            <section className="bg-surface border border-border rounded-xl p-5 space-y-4">
              <h3 className="text-body-lg font-bold text-on-surface">Embedding 嵌入模型配置</h3>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.embedder.use_remote}
                  onChange={(e) => updateField("embedder.use_remote", e.target.checked)}
                  className="accent-primary"
                />
                <span className="text-body-md">使用远程 API（取消则使用本地 sentence-transformers）</span>
              </label>
              <Field label="模型名称" value={config.embedder.model} onChange={(v) => updateField("embedder.model", v)} placeholder="sentence-transformers/all-MiniLM-L6-v2" />
              {!config.embedder.use_remote ? (
                <Field label="设备" value={config.embedder.device} onChange={(v) => updateField("embedder.device", v)} placeholder="cpu / cuda / cuda:0" />
              ) : (
                <>
                  <Field label="远程 Base URL" value={config.embedder.remote_base_url} onChange={(v) => updateField("embedder.remote_base_url", v)} placeholder="http://localhost:8000" />
                  <Field label="API Path" value={config.embedder.remote_api_path} onChange={(v) => updateField("embedder.remote_api_path", v)} placeholder="/v1/embeddings" />
                  <NumberField label="超时(秒)" value={config.embedder.remote_timeout} onChange={(v) => updateField("embedder.remote_timeout", v)} />
                </>
              )}
              <NumberField label="向量维度" value={config.embedder.dimension} onChange={(v) => updateField("embedder.dimension", v)} />
            </section>
          )}

          {/* Reranker 配置 */}
          {activeTab === "reranker" && (
            <section className="bg-surface border border-border rounded-xl p-5 space-y-4">
              <h3 className="text-body-lg font-bold text-on-surface">Reranker 重排序模型配置</h3>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.reranker.use_remote}
                  onChange={(e) => updateField("reranker.use_remote", e.target.checked)}
                  className="accent-primary"
                />
                <span className="text-body-md">使用远程 API（取消则使用本地 CrossEncoder）</span>
              </label>
              <Field label="模型名称" value={config.reranker.model} onChange={(v) => updateField("reranker.model", v)} placeholder="cross-encoder/ms-marco-MiniLM-L-6-v2" />
              {!config.reranker.use_remote ? (
                <Field label="设备" value={config.reranker.device} onChange={(v) => updateField("reranker.device", v)} placeholder="cpu / cuda" />
              ) : (
                <>
                  <Field label="远程 Base URL" value={config.reranker.remote_base_url} onChange={(v) => updateField("reranker.remote_base_url", v)} placeholder="https://your-reranker-api.com" />
                  <Field label="API Path" value={config.reranker.remote_api_path} onChange={(v) => updateField("reranker.remote_api_path", v)} placeholder="/v1/rerank" />
                  <NumberField label="超时(秒)" value={config.reranker.remote_timeout} onChange={(v) => updateField("reranker.remote_timeout", v)} />
                </>
              )}
            </section>
          )}

          {/* 系统参数 */}
          {activeTab === "system" && (
            <section className="bg-surface border border-border rounded-xl p-5 space-y-4">
              <h3 className="text-body-lg font-bold text-on-surface">系统参数</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <NumberField label="分块最大 Token" value={config.system.chunk_max_tokens} onChange={(v) => updateField("system.chunk_max_tokens", v)} />
                <NumberField label="会话时间间隔(秒)" value={config.system.session_time_gap_seconds} onChange={(v) => updateField("system.session_time_gap_seconds", v)} />
                <NumberField label="会话检测间隔" value={config.system.session_check_interval} onChange={(v) => updateField("system.session_check_interval", v)} />
                <NumberField label="最大待处理" value={config.system.session_max_pending} onChange={(v) => updateField("system.session_max_pending", v)} />
                <NumberField label="相似度 TopK" value={config.system.similarity_top_k} onChange={(v) => updateField("system.similarity_top_k", v)} />
                <NumberField label="相似度阈值" value={config.system.similarity_threshold} onChange={(v) => updateField("system.similarity_threshold", v)} step={0.05} />
                <NumberField label="相似度窗口" value={config.system.similarity_recent_window} onChange={(v) => updateField("system.similarity_recent_window", v)} />
                <NumberField label="BFS 每种子数" value={config.system.bfs_expansion_per_seed} onChange={(v) => updateField("system.bfs_expansion_per_seed", v)} />
                <NumberField label="BFS 跳数" value={config.system.bfs_expansion_hops} onChange={(v) => updateField("system.bfs_expansion_hops", v)} />
                <NumberField label="最大上下文单元" value={config.system.max_context_units} onChange={(v) => updateField("system.max_context_units", v)} />
                <NumberField label="最大实体数/LLM" value={config.system.max_entities_per_llm} onChange={(v) => updateField("system.max_entities_per_llm", v)} />
                <NumberField label="最大事件数/LLM" value={config.system.max_events_per_llm} onChange={(v) => updateField("system.max_events_per_llm", v)} />
                <NumberField label="索引升级阈值" value={config.system.promote_threshold} onChange={(v) => updateField("system.promote_threshold", v)} />
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.system.use_unified_pipeline}
                  onChange={(e) => updateField("system.use_unified_pipeline", e.target.checked)}
                  className="accent-primary"
                />
                <span className="text-body-md">使用统一管线（推荐）</span>
              </label>
            </section>
          )}

          {/* 操作按钮 */}
          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="bg-primary text-on-primary px-5 py-2.5 rounded-lg font-bold text-body-md hover:bg-opacity-90 disabled:opacity-50"
            >
              {isSaving ? "保存中..." : "保存并应用"}
            </button>
            <button
              onClick={handleReconfigure}
              disabled={isSaving}
              className="bg-secondary-container text-on-secondary-container px-4 py-2.5 rounded-lg font-medium text-body-md hover:bg-opacity-80 disabled:opacity-50"
            >
              热重载
            </button>
            <button
              onClick={handleTest}
              className="bg-surface-container text-on-surface-variant px-4 py-2.5 rounded-lg font-medium text-body-md hover:bg-opacity-80"
            >
              测试连通性
            </button>
            {message && <span className="text-body-sm text-on-surface-variant">{message}</span>}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function Field({ label, value, onChange, placeholder, type = "text" }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <div>
      <label className="text-body-sm text-on-surface-variant block mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-4 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary"
      />
    </div>
  );
}

function NumberField({ label, value, onChange, step }: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
}) {
  return (
    <div>
      <label className="text-body-sm text-on-surface-variant block mb-1">{label}</label>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        step={step}
        className="w-full px-4 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary"
      />
    </div>
  );
}
