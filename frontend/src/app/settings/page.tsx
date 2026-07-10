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
    local_path: string;
    offline_only: boolean;
  };
  reranker: {
    model: string;
    device: string;
    use_remote: boolean;
    remote_base_url: string;
    remote_api_path: string;
    remote_timeout: number;
    local_path: string;
    offline_only: boolean;
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
  external_stores: {
    milvus: {
      uri: string;
      user: string;
      password: string;
      db_name: string;
      collection: string;
      token: string;
      secure: boolean;
      remote_enabled: boolean;
    };
    neo4j: {
      uri: string;
      user: string;
      password: string;
      database: string;
    };
  };
}

export default function SettingsPage() {
  const [config, setConfig] = useState<MandolConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [activeTab, setActiveTab] = useState<
    | "llm"
    | "model_profiles"
    | "embedder"
    | "reranker"
    | "system"
    | "vector_db"
  >("model_profiles");

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setIsLoading(true);
    try {
      const data = await api.get<{ mandol: MandolConfig; is_ready: boolean }>("settings/config");
      // 兼容旧后端：补齐新增字段
      const m = data.mandol;
      m.embedder.local_path = m.embedder.local_path ?? "";
      m.embedder.offline_only = m.embedder.offline_only ?? false;
      m.reranker.local_path = m.reranker.local_path ?? "";
      m.reranker.offline_only = m.reranker.offline_only ?? false;
      if (!m.external_stores) {
        (m as any).external_stores = {
          milvus: { uri: "", user: "", password: "", db_name: "", collection: "mandol_memory_units", token: "", secure: false, remote_enabled: true },
          neo4j: { uri: "", user: "", password: "", database: "" },
        };
      }
      setConfig(m);
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
          <div className="flex items-center gap-2 border-b border-border flex-wrap">
            {[
              { key: "model_profiles" as const, label: "问答模型（多源）", icon: "hub" },
              { key: "llm" as const, label: "Mandol LLM", icon: "smart_toy" },
              { key: "embedder" as const, label: "Embedding 嵌入模型", icon: "data_object" },
              { key: "reranker" as const, label: "Reranker 重排序模型", icon: "sort" },
              { key: "vector_db" as const, label: "向量库 / 图数据库", icon: "storage" },
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

          {/* 问答模型（多源）配置 */}
          {activeTab === "model_profiles" && (
            <LLMProfileManager />
          )}

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
              <LocalModelSelector
                kind="embedder"
                config={config}
                updateField={updateField}
                onMessage={setMessage}
                showOfflineHint={!config.embedder.use_remote}
              />
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
              <LocalModelSelector
                kind="reranker"
                config={config}
                updateField={updateField}
                onMessage={setMessage}
                showOfflineHint={!config.reranker.use_remote}
              />
            </section>
          )}

          {/* 向量库 / 图数据库 */}
          {activeTab === "vector_db" && (
            <VectorDbConfig config={config} updateField={updateField} setMessage={setMessage} />
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

// =============== 向量库 / 图数据库配置 ===============

function VectorDbConfig({
  config,
  updateField,
  setMessage,
}: {
  config: MandolConfig;
  updateField: (path: string, value: any) => void;
  setMessage: (m: string) => void;
}) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    milvus: { available: boolean; uri: string; collections?: string[]; error?: string | null };
    neo4j: { available: boolean; uri: string; error?: string | null };
  } | null>(null);

  const handleTest = async () => {
    setTesting(true);
    setMessage("");
    setTestResult(null);
    try {
      // 先把当前编辑值同步到 settings（通过保存接口走个来回），再测试
      // 这里直接测试当前 settings 中的值（后端读取的是 settings.mandol_milvus_*）
      const data = await api.post<{
        milvus: { available: boolean; uri: string; collections?: string[]; error?: string | null };
        neo4j: { available: boolean; uri: string; error?: string | null };
      }>("settings/external-stores/test");
      setTestResult(data);
      const m = data.milvus.available ? "✓" : "✗";
      const n = data.neo4j.available ? "✓" : "✗";
      setMessage(`Milvus: ${m} | Neo4j: ${n}`);
    } catch (err) {
      setMessage(`连通性测试失败: ${err instanceof ApiError ? err.detail : "未知错误"}`);
    } finally {
      setTesting(false);
    }
  };

  const m = config.external_stores?.milvus ?? {
    uri: "",
    user: "",
    password: "",
    db_name: "",
    collection: "mandol_memory_units",
    token: "",
    secure: false,
    remote_enabled: true,
  };
  const n4j = config.external_stores?.neo4j ?? {
    uri: "",
    user: "",
    password: "",
    database: "",
  };
  return (
    <section className="space-y-4">
      <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-body-lg font-bold text-on-surface">Milvus 向量数据库</h3>
            <p className="text-body-sm text-on-surface-variant mt-1">
              用于存储记忆单元的稠密向量，支持 Milvus Lite（本地文件）或远程 Milvus Server。
              配置会持久化到 <code className="text-body-sm bg-surface-container px-1 rounded">external_stores.yaml</code>，
              下次启动自动应用。
            </p>
          </div>
          <span className="text-label-sm px-2 py-0.5 rounded bg-primary/10 text-primary">持久化生效</span>
        </div>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={m.remote_enabled}
            onChange={(e) => updateField("external_stores.milvus.remote_enabled", e.target.checked)}
            className="accent-primary"
          />
          <span className="text-body-md">使用远程 Milvus Server（取消则回退到本地嵌入式 milvus.db）</span>
        </label>
        <Field
          label={m.remote_enabled ? "Milvus URI" : "本地 db 文件路径"}
          value={m.uri}
          onChange={(v) => updateField("external_stores.milvus.uri", v)}
          placeholder={m.remote_enabled ? "http://localhost:19530" : "data/mandol/milvus.db"}
        />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="用户名" value={m.user} onChange={(v) => updateField("external_stores.milvus.user", v)} placeholder="（无则留空）" />
          <Field label="密码" value={m.password} onChange={(v) => updateField("external_stores.milvus.password", v)} placeholder="（无则留空，*** 表示已保存）" type="password" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="数据库名" value={m.db_name} onChange={(v) => updateField("external_stores.milvus.db_name", v)} placeholder="（使用默认则留空）" />
          <Field label="Collection 名" value={m.collection} onChange={(v) => updateField("external_stores.milvus.collection", v)} placeholder="mandol_memory_units" />
        </div>
        <Field label="Token (鉴权用)" value={m.token} onChange={(v) => updateField("external_stores.milvus.token", v)} placeholder="（无则留空，*** 表示已保存）" type="password" />
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={m.secure}
            onChange={(e) => updateField("external_stores.milvus.secure", e.target.checked)}
            className="accent-primary"
          />
          <span className="text-body-md">使用 HTTPS（远程模式）</span>
        </label>
      </div>

      <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-body-lg font-bold text-on-surface">Neo4j 图数据库</h3>
            <p className="text-body-sm text-on-surface-variant mt-1">
              用于实体/事件/关系图谱存储。配置同样持久化到
              <code className="text-body-sm bg-surface-container px-1 rounded mx-1">external_stores.yaml</code>。
            </p>
          </div>
        </div>
        <Field label="Bolt URI" value={n4j.uri} onChange={(v) => updateField("external_stores.neo4j.uri", v)} placeholder="bolt://localhost:7687" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="用户名" value={n4j.user} onChange={(v) => updateField("external_stores.neo4j.user", v)} placeholder="neo4j" />
          <Field label="密码" value={n4j.password} onChange={(v) => updateField("external_stores.neo4j.password", v)} placeholder="（无则留空，*** 表示已保存）" type="password" />
        </div>
        <Field label="数据库名" value={n4j.database} onChange={(v) => updateField("external_stores.neo4j.database", v)} placeholder="neo4j" />
      </div>

      <div className="bg-surface border border-border rounded-xl p-4 flex items-center gap-3 flex-wrap">
        <button
          onClick={handleTest}
          disabled={testing}
          className="bg-secondary-container text-on-secondary-container px-4 py-2 rounded-lg font-medium text-body-md hover:bg-opacity-80 disabled:opacity-50"
        >
          {testing ? "测试中..." : "测试连接"}
        </button>
        <span className="text-body-sm text-on-surface-variant">
          提示：点击「测试连接」会使用 settings 中已保存的值；如修改了上面表单，请先「保存并应用」。
        </span>
        {testResult && (
          <div className="w-full mt-2 text-body-sm">
            <div className={testResult.milvus.available ? "text-success" : "text-error"}>
              Milvus {testResult.milvus.available ? "✓ 可用" : "✗ 不可用"} ({testResult.milvus.uri})
              {testResult.milvus.error ? ` - ${testResult.milvus.error}` : ""}
              {testResult.milvus.collections && testResult.milvus.collections.length > 0
                ? ` - collections: ${testResult.milvus.collections.join(", ")}`
                : ""}
            </div>
            <div className={testResult.neo4j.available ? "text-success" : "text-error"}>
              Neo4j {testResult.neo4j.available ? "✓ 可用" : "✗ 不可用"} ({testResult.neo4j.uri})
              {testResult.neo4j.error ? ` - ${testResult.neo4j.error}` : ""}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

// =============== 本地模型选择器（嵌入到 Embedder / Reranker 配置中） ===============

interface LocalModel {
  id: string;
  path: string;
  root: string;
}

function LocalModelSelector({
  kind,
  config,
  updateField,
  onMessage,
  showOfflineHint = true,
}: {
  kind: "embedder" | "reranker";
  config: MandolConfig;
  updateField: (path: string, value: any) => void;
  onMessage: (m: string) => void;
  showOfflineHint?: boolean;
}) {
  const [localModels, setLocalModels] = useState<LocalModel[]>([]);
  const [scanning, setScanning] = useState(false);
  const [selectedPath, setSelectedPath] = useState<string>(
    kind === "embedder" ? config.embedder.local_path : config.reranker.local_path
  );
  const [picking, setPicking] = useState(false);

  const sub = kind === "embedder" ? config.embedder : config.reranker;
  const subKey = kind; // "embedder" | "reranker"

  const filterMatches = (m: LocalModel) => {
    const id = m.id.toLowerCase();
    if (kind === "embedder") {
      return (
        id.includes("embed") ||
        id.includes("minilm") ||
        id.includes("bge") ||
        id.includes("gte") ||
        id.includes("mpnet") ||
        id.includes("e5") ||
        id.includes("sentence")
      );
    }
    return (
      id.includes("rerank") ||
      id.includes("cross") ||
      id.includes("marco")
    );
  };

  const scan = async () => {
    setScanning(true);
    try {
      const data = await api.get<{ models: LocalModel[]; roots: string[]; hf_home: string }>(
        "system/models/local"
      );
      setLocalModels((data.models || []).filter(filterMatches));
    } catch (err) {
      onMessage(`扫描本地模型失败: ${err instanceof ApiError ? err.detail : (err as Error).message}`);
    } finally {
      setScanning(false);
    }
  };

  useEffect(() => {
    scan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind]);

  useEffect(() => {
    setSelectedPath(sub.local_path || "");
  }, [sub.local_path]);

  const handlePick = async (path: string) => {
    setPicking(true);
    try {
      await api.post("system/models/select-local", { kind, path });
      // 同步到主配置 form
      updateField(`${subKey}.local_path`, path);
      updateField(`${subKey}.offline_only`, true);
      setSelectedPath(path);
      onMessage(`已为 ${kind === "embedder" ? "Embedding" : "Reranker"} 选择本地模型，下次启动会从本地路径加载`);
    } catch (err) {
      onMessage(`选择失败: ${err instanceof ApiError ? err.detail : (err as Error).message}`);
    } finally {
      setPicking(false);
    }
  };

  const handleClear = async () => {
    setPicking(true);
    try {
      await api.post("system/models/clear-local", { kind });
      updateField(`${subKey}.local_path`, "");
      updateField(`${subKey}.offline_only`, false);
      setSelectedPath("");
      onMessage(`已清除 ${kind === "embedder" ? "Embedding" : "Reranker"} 的本地模型选择（回退到 ${sub.model}）`);
    } catch (err) {
      onMessage(`清除失败: ${err instanceof ApiError ? err.detail : (err as Error).message}`);
    } finally {
      setPicking(false);
    }
  };

  const toggleOffline = (v: boolean) => {
    updateField(`${subKey}.offline_only`, v);
  };

  return (
    <div className="bg-surface-container-low rounded-lg p-4 space-y-3 border border-border">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h4 className="text-body-md font-semibold text-on-surface flex items-center gap-1">
            <Icon name="folder_zip" className="text-[16px]" />
            本地缓存模型
            <span className="text-label-sm px-1.5 py-0.5 rounded bg-primary/10 text-primary font-normal">
              离线拉起
            </span>
          </h4>
          {showOfflineHint && (
            <p className="text-body-sm text-on-surface-variant mt-1">
              从本地 HF 缓存（~/.cache/huggingface）或 <code>data/models/</code> 选用已下载的模型。
              启用后可避免每次启动时从远端下载。
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={scan}
          disabled={scanning}
          className="text-body-sm bg-surface text-on-surface px-2 py-1 rounded-md hover:bg-surface-container-high disabled:opacity-50 whitespace-nowrap"
        >
          <Icon name="refresh" className="text-[14px] inline-block mr-1" />
          {scanning ? "扫描中…" : "刷新"}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-2 items-end">
        <div>
          <label className="block text-body-sm text-on-surface-variant mb-1">当前本地路径</label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={selectedPath || ""}
              onChange={(e) => setSelectedPath(e.target.value)}
              onBlur={() => updateField(`${subKey}.local_path`, selectedPath)}
              placeholder="（未选择：使用上方「模型名称」从远端加载）"
              className="flex-1 bg-surface text-on-surface border border-border rounded-md px-3 py-2 text-body-sm font-mono"
            />
            {selectedPath && (
              <button
                type="button"
                onClick={handleClear}
                disabled={picking}
                className="text-body-sm text-error hover:underline whitespace-nowrap"
              >
                清除
              </button>
            )}
          </div>
        </div>
        <label className="flex items-center gap-2 cursor-pointer whitespace-nowrap pb-2">
          <input
            type="checkbox"
            checked={!!sub.offline_only}
            onChange={(e) => toggleOffline(e.target.checked)}
            className="w-4 h-4 accent-primary"
          />
          <span className="text-body-sm">强制离线（不联网）</span>
        </label>
      </div>

      {localModels.length === 0 ? (
        <p className="text-body-sm text-on-surface-variant p-2 bg-surface rounded-md">
          {scanning ? "正在扫描本地模型…" : "未在本地找到匹配的模型。点击「刷新」重新扫描，或把模型放到 HF 缓存 / data/models 下。"}
        </p>
      ) : (
        <div className="space-y-1 max-h-60 overflow-y-auto custom-scrollbar">
          {localModels.map((m) => {
            const isCurrent = selectedPath === m.path || sub.local_path === m.path;
            return (
              <div
                key={m.path}
                className={[
                  "flex items-center gap-2 p-2 rounded-md border text-body-sm",
                  isCurrent
                    ? "border-primary bg-primary-container/30"
                    : "border-border bg-surface hover:bg-surface-container",
                ].join(" ")}
              >
                <div className="flex-1 min-w-0">
                  <div className="text-on-surface font-medium truncate" title={m.id}>
                    {m.id}
                  </div>
                  <div className="text-on-surface-variant font-mono truncate text-[12px]" title={m.path}>
                    {m.path}
                  </div>
                </div>
                {isCurrent ? (
                  <span className="text-primary font-semibold whitespace-nowrap text-body-sm">✓ 当前</span>
                ) : (
                  <button
                    type="button"
                    onClick={() => handlePick(m.path)}
                    disabled={picking}
                    className="bg-primary text-on-primary px-3 py-1 rounded-md text-body-sm font-medium hover:opacity-90 disabled:opacity-50 whitespace-nowrap"
                  >
                    选用
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// =============== LLM Profile 管理 ===============

import type { LLMProfile } from "@/types";

interface LLMProfileForm {
  id?: string;
  name: string;
  provider: string;
  base_url: string;
  model: string;
  api_key: string;
  temperature: number;
  max_tokens: number;
  timeout_s: number;
  enabled: boolean;
  is_default: boolean;
}

const EMPTY_PROFILE: LLMProfileForm = {
  name: "",
  provider: "openai",
  base_url: "https://api.openai.com/v1",
  model: "gpt-4o-mini",
  api_key: "",
  temperature: 0.3,
  max_tokens: 1024,
  timeout_s: 60,
  enabled: true,
  is_default: false,
};

function LLMProfileManager() {
  const [profiles, setProfiles] = useState<LLMProfile[]>([]);
  const [editing, setEditing] = useState<LLMProfileForm | null>(null);
  const [editingErr, setEditingErr] = useState("");  // 模态框内错误（保存失败时显示）
  const [saving, setSaving] = useState(false);        // 保存中 loading
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { ok: boolean; msg: string }>>({});
  const [msg, setMsg] = useState("");

  const load = async () => {
    try {
      const list = await api.get<LLMProfile[]>("llm/profiles");
      setProfiles(list || []);
    } catch (err) {
      setMsg(`加载失败: ${(err as Error).message}`);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const startNew = () => {
    setEditing({ ...EMPTY_PROFILE });
  };

  const startEdit = (p: LLMProfile) => {
    setEditing({
      id: p.id,
      name: p.name,
      provider: p.provider,
      base_url: p.base_url,
      model: p.model,
      api_key: p.api_key || "",
      temperature: p.temperature,
      max_tokens: p.max_tokens,
      timeout_s: p.timeout_s,
      enabled: p.enabled,
      is_default: p.is_default,
    });
  };

  const saveProfile = async () => {
    if (!editing) return;
    if (!editing.name || !editing.base_url || !editing.model) {
      setEditingErr("名称 / Base URL / 模型为必填");
      return;
    }
    setEditingErr("");
    setSaving(true);
    try {
      // 后端只有 POST /api/llm/profiles（通用 upsert），不要把 id 拼到 URL，
      // 否则会请求 /api/llm/profiles/<id>（该路由不存在 → 404 看似无响应）
      await api.post<LLMProfile>(`llm/profiles`, editing);
      setEditing(null);
      setMsg("已保存");
      await load();
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : (err as Error).message;
      setEditingErr(`保存失败: ${detail}`);
    } finally {
      setSaving(false);
    }
  };

  const deleteProfile = async (id: string) => {
    if (!confirm("确定删除该模型源？")) return;
    try {
      await api.del(`llm/profiles/${id}`);
      await load();
    } catch (err) {
      setMsg(`删除失败: ${(err as Error).message}`);
    }
  };

  const setDefault = async (id: string) => {
    try {
      await api.post<LLMProfile>(`llm/profiles/${id}/default`);
      await load();
    } catch (err) {
      setMsg(`设默认失败: ${(err as Error).message}`);
    }
  };

  const testProfile = async (id: string) => {
    setTesting(id);
    setMsg("");
    try {
      const r = await api.post<{ ok: boolean; status?: number; snippet?: string; error?: string }>(
        `llm/profiles/${id}/test`,
      );
      setTestResults((prev) => ({
        ...prev,
        [id]: {
          ok: !!r.ok,
          msg: r.ok
            ? `✓ HTTP ${r.status} - ${(r.snippet || "").slice(0, 50)}`
            : `✗ ${r.error || `HTTP ${r.status || "?"}`}`,
        },
      }));
    } catch (err) {
      setTestResults((prev) => ({
        ...prev,
        [id]: { ok: false, msg: `✗ ${(err as Error).message}` },
      }));
    } finally {
      setTesting(null);
    }
  };

  return (
    <section className="bg-surface border border-border rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-body-lg font-bold text-on-surface">问答模型（多源）</h3>
          <p className="text-body-sm text-on-surface-variant mt-1">
            添加多个 OpenAI 兼容模型源（OpenAI、Azure、Ollama、vLLM、DeepSeek 等），问答时可按需切换
          </p>
        </div>
        <button
          onClick={startNew}
          className="bg-primary text-on-primary px-4 py-2 rounded-lg text-body-md font-medium inline-flex items-center gap-1 hover:opacity-90"
        >
          <Icon name="add" /> 新增模型
        </button>
      </div>

      {msg && (
        <div className="bg-surface-container-low border border-border rounded px-3 py-2 text-label-sm text-on-surface-variant">
          {msg}
        </div>
      )}

      {/* 列表 */}
      <div className="space-y-2">
        {profiles.length === 0 && (
          <p className="text-label-sm text-on-surface-variant text-center py-6">
            还没有模型源，点击右上角「新增模型」添加
          </p>
        )}
        {profiles.map((p) => {
          const test = testResults[p.id];
          return (
            <div
              key={p.id}
              className={[
                "border rounded-lg p-3 flex items-start gap-3",
                p.is_default ? "border-primary bg-primary-fixed/30" : "border-border",
                !p.enabled ? "opacity-50" : "",
              ].join(" ")}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-body-md font-medium text-on-surface">
                    {p.name}
                  </p>
                  {p.is_default && (
                    <span className="px-1.5 py-0.5 bg-primary text-on-primary rounded text-label-sm">
                      默认
                    </span>
                  )}
                  {!p.enabled && (
                    <span className="px-1.5 py-0.5 bg-surface-container text-on-surface-variant rounded text-label-sm">
                      禁用
                    </span>
                  )}
                </div>
                <p className="text-label-sm text-on-surface-variant mt-0.5 truncate">
                  {p.provider} · {p.model} · {p.base_url}
                </p>
                {test && (
                  <p
                    className={[
                      "text-label-sm mt-1",
                      test.ok ? "text-success" : "text-error",
                    ].join(" ")}
                  >
                    {test.msg}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-1.5 flex-shrink-0">
                {!p.is_default && (
                  <button
                    onClick={() => setDefault(p.id)}
                    className="px-2 py-1 text-label-sm border border-border rounded hover:bg-surface-container-low"
                    title="设为默认"
                  >
                    设默认
                  </button>
                )}
                <button
                  onClick={() => testProfile(p.id)}
                  disabled={testing === p.id}
                  className="px-2 py-1 text-label-sm border border-border rounded hover:bg-surface-container-low inline-flex items-center gap-1"
                  title="测试连通性"
                >
                  {testing === p.id ? <Loading size="sm" /> : <Icon name="bolt" className="text-[14px]" />}
                  测试
                </button>
                <button
                  onClick={() => startEdit(p)}
                  className="p-1.5 text-on-surface-variant hover:text-primary"
                  title="编辑"
                >
                  <Icon name="edit" className="text-[16px]" />
                </button>
                <button
                  onClick={() => deleteProfile(p.id)}
                  className="p-1.5 text-on-surface-variant hover:text-error"
                  title="删除"
                >
                  <Icon name="delete" className="text-[16px]" />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* 编辑表单 */}
      {editing && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-surface border border-border rounded-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 space-y-3">
            <h4 className="text-body-lg font-bold">
              {editing.id ? "编辑模型源" : "新增模型源"}
            </h4>
            <div className="grid grid-cols-2 gap-3">
              <Field
                label="显示名称 *"
                value={editing.name}
                onChange={(v) => setEditing({ ...editing, name: v })}
                placeholder="GPT-4o / DeepSeek / Ollama-Llama3"
              />
              <Field
                label="Provider"
                value={editing.provider}
                onChange={(v) => setEditing({ ...editing, provider: v })}
                placeholder="openai / ollama / azure / deepseek"
              />
            </div>
            <Field
              label="Base URL *"
              value={editing.base_url}
              onChange={(v) => setEditing({ ...editing, base_url: v })}
              placeholder="https://api.openai.com/v1  或  http://localhost:11434/v1"
            />
            <Field
              label="模型 *"
              value={editing.model}
              onChange={(v) => setEditing({ ...editing, model: v })}
              placeholder="gpt-4o-mini / llama3.1:8b / deepseek-chat"
            />
            <Field
              label="API Key"
              value={editing.api_key === "***" ? "" : editing.api_key}
              onChange={(v) => setEditing({ ...editing, api_key: v })}
              placeholder="sk-...  留空 = 不修改 / 公开模型可不填"
              type="password"
            />
            <div className="grid grid-cols-3 gap-3">
              <NumberField
                label="Temperature"
                value={editing.temperature}
                onChange={(v) => setEditing({ ...editing, temperature: v })}
                step={0.1}
              />
              <NumberField
                label="Max Tokens"
                value={editing.max_tokens}
                onChange={(v) => setEditing({ ...editing, max_tokens: v })}
              />
              <NumberField
                label="超时(秒)"
                value={editing.timeout_s}
                onChange={(v) => setEditing({ ...editing, timeout_s: v })}
              />
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-body-sm">
                <input
                  type="checkbox"
                  checked={editing.enabled}
                  onChange={(e) => setEditing({ ...editing, enabled: e.target.checked })}
                />
                启用
              </label>
              <label className="flex items-center gap-2 text-body-sm">
                <input
                  type="checkbox"
                  checked={editing.is_default}
                  onChange={(e) => setEditing({ ...editing, is_default: e.target.checked })}
                />
                设为默认
              </label>
            </div>
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
              <button
                onClick={() => { setEditing(null); setEditingErr(""); }}
                className="px-3 py-2 text-body-sm border border-border rounded"
                disabled={saving}
              >
                取消
              </button>
              <button
                onClick={saveProfile}
                disabled={saving}
                className="px-3 py-2 text-body-sm bg-primary text-on-primary rounded inline-flex items-center gap-2 disabled:opacity-60"
              >
                {saving && <Loading size="sm" />}
                {saving ? "保存中…" : "保存"}
              </button>
            </div>
            {editingErr && (
              <div className="bg-error-container/30 border border-error/40 text-error rounded px-3 py-2 text-label-sm">
                {editingErr}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
