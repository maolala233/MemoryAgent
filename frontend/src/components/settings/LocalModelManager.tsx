"use client";
import { useEffect, useState } from "react";
import { Icon } from "@/components/shared/Icon";
import { api, ApiError } from "@/services/api";

interface LocalModel {
  id: string;
  path: string;
  root: string;
}

interface LocalModelsResponse {
  models: LocalModel[];
  roots: string[];
  hf_home: string;
}

interface CurrentModels {
  embedder: {
    model: string;
    local_path: string;
    offline_only: boolean;
    device: string;
    use_remote: boolean;
  };
  reranker: {
    model: string;
    local_path: string;
    offline_only: boolean;
    device: string;
    use_remote: boolean;
  };
  hf_offline: boolean;
  hf_home: string;
}

export function LocalModelManager() {
  const [data, setData] = useState<LocalModelsResponse | null>(null);
  const [current, setCurrent] = useState<CurrentModels | null>(null);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");
  const [activeKind, setActiveKind] = useState<"embedder" | "reranker">("embedder");
  const [hfOffline, setHfOffline] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [d1, d2] = await Promise.all([
        api.get<LocalModelsResponse>("system/models/local"),
        api.get<CurrentModels>("system/models/current"),
      ]);
      setData(d1);
      setCurrent(d2);
      setHfOffline(d2.hf_offline);
    } catch (err) {
      setMsg(`加载失败: ${err instanceof ApiError ? err.detail : (err as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleSelect = async (path: string) => {
    setMsg("");
    try {
      await api.post("system/models/select-local", { kind: activeKind, path });
      setMsg(`已为 ${activeKind} 选择本地模型：${path}`);
      await load();
    } catch (err) {
      setMsg(`选择失败: ${err instanceof ApiError ? err.detail : (err as Error).message}`);
    }
  };

  const handleClear = async () => {
    setMsg("");
    try {
      await api.post("system/models/clear-local", { kind: activeKind });
      setMsg(`已清除 ${activeKind} 本地模型选择（回退到远端/默认）`);
      await load();
    } catch (err) {
      setMsg(`清除失败: ${err instanceof ApiError ? err.detail : (err as Error).message}`);
    }
  };

  const handleOfflineToggle = async (enabled: boolean) => {
    setMsg("");
    try {
      await api.post("system/models/offline", { enabled });
      setHfOffline(enabled);
      setMsg(enabled ? "已开启 HF 离线模式（仅使用本地缓存模型）" : "已关闭 HF 离线模式");
    } catch (err) {
      setMsg(`切换失败: ${err instanceof ApiError ? err.detail : (err as Error).message}`);
    }
  };

  if (loading) {
    return (
      <section className="bg-surface border border-border rounded-xl p-5">
        <p className="text-on-surface-variant">加载本地模型列表中…</p>
      </section>
    );
  }

  const filtered = (data?.models || []).filter((m) => {
    const id = m.id.toLowerCase();
    if (activeKind === "embedder") {
      return (
        id.includes("embed") ||
        id.includes("minilm") ||
        id.includes("bge") ||
        id.includes("gte") ||
        id.includes("mpnet") ||
        id.includes("e5")
      );
    }
    return (
      id.includes("rerank") ||
      id.includes("cross") ||
      id.includes("marco")
    );
  });

  const currentPath =
    activeKind === "embedder" ? current?.embedder.local_path : current?.reranker.local_path;
  const currentOffline =
    activeKind === "embedder" ? current?.embedder.offline_only : current?.reranker.offline_only;

  return (
    <section className="bg-surface border border-border rounded-xl p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-body-lg font-bold text-on-surface flex items-center gap-2">
            <Icon name="folder_zip" className="text-[18px]" />
            本地模型管理（离线/已下载）
          </h3>
          <p className="text-body-sm text-on-surface-variant mt-1">
            在没有网络或不想每次启动都下载模型时，扫描本地已有模型并指定为 embedder / reranker。
            模型目录来源：HF 缓存（{data?.hf_home || "~/.cache/huggingface"}）+ <code>data/models</code>
          </p>
        </div>
        <button
          onClick={load}
          className="text-body-sm bg-surface-container text-on-surface px-3 py-1.5 rounded-lg hover:bg-surface-container-high"
        >
          <Icon name="refresh" className="text-[14px] inline-block mr-1" />
          刷新
        </button>
      </div>

      {/* 离线开关 */}
      <div className="flex items-center gap-3 p-3 bg-surface-container-low rounded-lg">
        <input
          id="hf-offline"
          type="checkbox"
          checked={hfOffline}
          onChange={(e) => handleOfflineToggle(e.target.checked)}
          className="w-4 h-4 accent-primary"
        />
        <label htmlFor="hf-offline" className="text-body-md cursor-pointer flex-1">
          HuggingFace 全局离线模式
          <span className="block text-body-sm text-on-surface-variant">
            开启后只使用本地缓存中的模型，不再访问 huggingface.co
          </span>
        </label>
      </div>

      {/* Kind 切换 */}
      <div className="flex items-center gap-2">
        {(
          [
            { k: "embedder" as const, label: "Embedding 模型" },
            { k: "reranker" as const, label: "Reranker 模型" },
          ]
        ).map((t) => (
          <button
            key={t.k}
            onClick={() => setActiveKind(t.k)}
            className={[
              "px-3 py-1.5 rounded-lg text-body-sm font-medium",
              activeKind === t.k
                ? "bg-primary text-on-primary"
                : "bg-surface-container text-on-surface-variant hover:bg-surface-container-high",
            ].join(" ")}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 当前选择 */}
      <div className="bg-surface-container-low rounded-lg p-3 text-body-sm space-y-1">
        <div className="text-on-surface-variant">当前 {activeKind}：</div>
        <div>
          <span className="text-on-surface-variant">远端模型：</span>
          <span className="font-mono">
            {activeKind === "embedder" ? current?.embedder.model : current?.reranker.model}
          </span>
        </div>
        <div>
          <span className="text-on-surface-variant">本地路径：</span>
          <span className="font-mono">{currentPath || "（未设置）"}</span>
        </div>
        <div>
          <span className="text-on-surface-variant">强制离线：</span>
          <span>{currentOffline ? "✓ 是" : "✗ 否"}</span>
        </div>
        {currentPath && (
          <button
            onClick={handleClear}
            className="mt-2 text-body-sm text-error hover:underline"
          >
            清除本地选择（回退到远端/默认）
          </button>
        )}
      </div>

      {/* 本地模型列表 */}
      <div>
        <h4 className="text-body-md font-semibold text-on-surface mb-2">
          候选模型（{filtered.length}）
        </h4>
        {filtered.length === 0 ? (
          <p className="text-body-sm text-on-surface-variant p-3 bg-surface-container-low rounded-lg">
            未在本地找到匹配的 {activeKind} 模型。请先把模型下载到
            <code className="mx-1">{data?.hf_home || "HF 缓存"}</code>
            或 <code>data/models/&lt;model-name&gt;</code> 目录，然后点击右上角「刷新」。
          </p>
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto custom-scrollbar">
            {filtered.map((m) => (
              <div
                key={m.path}
                className={[
                  "flex items-center gap-3 p-3 rounded-lg border",
                  currentPath === m.path
                    ? "border-primary bg-primary-container/30"
                    : "border-border bg-surface-container-low hover:bg-surface-container",
                ].join(" ")}
              >
                <div className="flex-1 min-w-0">
                  <div className="text-body-md text-on-surface font-medium truncate" title={m.id}>
                    {m.id}
                  </div>
                  <div className="text-body-sm text-on-surface-variant font-mono truncate" title={m.path}>
                    {m.path}
                  </div>
                </div>
                {currentPath === m.path ? (
                  <span className="text-body-sm text-primary font-semibold whitespace-nowrap">
                    ✓ 当前
                  </span>
                ) : (
                  <button
                    onClick={() => handleSelect(m.path)}
                    className="bg-primary text-on-primary px-3 py-1.5 rounded-lg text-body-sm font-medium hover:opacity-90 whitespace-nowrap"
                  >
                    选用
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {msg && (
        <p className="text-body-sm text-on-surface-variant bg-surface-container-low rounded p-2">
          {msg}
        </p>
      )}
    </section>
  );
}
