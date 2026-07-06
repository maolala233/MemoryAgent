"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { Pill } from "@/components/shared/Pill";
import { api, ApiError } from "@/services/api";

interface SystemInfo {
  status: string;
  version: string;
  vault_dir: string;
  db_path: string;
  llm_provider: string;
  embedding_provider: string;
  agents_count: number;
  docs_count: number;
}

export default function SettingsPage() {
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<SystemInfo>("system")
      .then(setInfo)
      .catch((err) =>
        setError(err instanceof ApiError ? err.detail : "Failed to load system info"),
      )
      .finally(() => setIsLoading(false));
  }, []);

  const onRescan = async () => {
    try {
      await api.post("memory/rescan");
      alert("Vault rescan triggered.");
    } catch (err) {
      alert(err instanceof ApiError ? err.detail : "Rescan failed");
    }
  };

  return (
    <AppShell title="Settings" subtitle="System configuration">
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="max-w-3xl mx-auto px-panel-padding py-8 space-y-6">
          {error && (
            <div className="bg-error/10 border border-error/20 text-error rounded-lg p-3 flex items-center gap-2">
              <Icon name="error" filled />
              <span className="text-body-md">{error}</span>
            </div>
          )}

          {isLoading && <Loading size="lg" label="Loading settings..." />}

          {info && (
            <>
              <div className="bg-surface border border-border rounded-xl p-6">
                <h3 className="text-body-lg font-bold text-on-surface mb-4">
                  System Information
                </h3>
                <dl className="grid grid-cols-2 gap-4">
                  <div>
                    <dt className="text-label-md text-on-surface-variant">Status</dt>
                    <dd className="flex items-center gap-2 mt-1">
                      <Pill variant="success" size="md">
                        <span className="w-1.5 h-1.5 bg-success rounded-full" />
                        {info.status}
                      </Pill>
                    </dd>
                  </div>
                  <div>
                    <dt className="text-label-md text-on-surface-variant">Version</dt>
                    <dd className="text-body-md font-mono mt-1">{info.version}</dd>
                  </div>
                  <div>
                    <dt className="text-label-md text-on-surface-variant">
                      Vault Directory
                    </dt>
                    <dd className="text-body-sm font-mono mt-1 break-all">
                      {info.vault_dir}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-label-md text-on-surface-variant">
                      Database Path
                    </dt>
                    <dd className="text-body-sm font-mono mt-1 break-all">
                      {info.db_path}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-label-md text-on-surface-variant">
                      LLM Provider
                    </dt>
                    <dd className="mt-1">
                      <Pill variant="info" size="md">
                        {info.llm_provider}
                      </Pill>
                    </dd>
                  </div>
                  <div>
                    <dt className="text-label-md text-on-surface-variant">
                      Embedding Provider
                    </dt>
                    <dd className="mt-1">
                      <Pill variant="info" size="md">
                        {info.embedding_provider}
                      </Pill>
                    </dd>
                  </div>
                  <div>
                    <dt className="text-label-md text-on-surface-variant">
                      Agents Configured
                    </dt>
                    <dd className="text-body-lg font-bold mt-1">
                      {info.agents_count}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-label-md text-on-surface-variant">
                      Total Memories
                    </dt>
                    <dd className="text-body-lg font-bold mt-1">{info.docs_count}</dd>
                  </div>
                </dl>
              </div>

              <div className="bg-surface border border-border rounded-xl p-6 space-y-3">
                <h3 className="text-body-lg font-bold text-on-surface">Actions</h3>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={onRescan}
                    className="px-4 py-2 bg-primary text-on-primary rounded-lg font-bold text-body-md hover:opacity-90 flex items-center gap-2"
                  >
                    <Icon name="refresh" className="text-[18px]" />
                    Rescan Vault
                  </button>
                </div>
                <p className="text-body-sm text-on-surface-variant">
                  Rescanning re-indexes all markdown files in the vault directory,
                  picking up external changes.
                </p>
              </div>

              <div className="bg-surface border border-border rounded-xl p-6">
                <h3 className="text-body-lg font-bold text-on-surface mb-3">
                  Configuration Files
                </h3>
                <p className="text-body-md text-on-surface-variant mb-3">
                  Edit these YAML files in <code className="font-mono text-primary">backend/config/</code> to customize:
                </p>
                <ul className="space-y-2">
                  {[
                    { file: "models.yaml", desc: "LLM & embedding providers" },
                    { file: "agents.yaml", desc: "Agent definitions & prompts" },
                    { file: "retrieval.yaml", desc: "Search strategy weights" },
                  ].map((c) => (
                    <li
                      key={c.file}
                      className="flex items-center gap-3 p-2 bg-surface-container-low rounded-lg"
                    >
                      <Icon
                        name="description"
                        className="text-on-surface-variant text-[20px]"
                      />
                      <div>
                        <p className="font-mono text-body-sm text-primary">{c.file}</p>
                        <p className="text-label-sm text-on-surface-variant">
                          {c.desc}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}
