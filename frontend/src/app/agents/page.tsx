"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { Pill } from "@/components/shared/Pill";
import { EmptyState } from "@/components/shared/EmptyState";
import { api, ApiError } from "@/services/api";
import type { AgentInfo } from "@/types";

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<
    Record<string, { ok: boolean; message: string }>
  >({});

  useEffect(() => {
    api
      .get<AgentInfo[]>("agents")
      .then(setAgents)
      .catch((err) =>
        setError(err instanceof ApiError ? err.detail : "Failed to load agents"),
      )
      .finally(() => setIsLoading(false));
  }, []);

  const onTest = async (id: string) => {
    setTesting(id);
    setError(null);
    try {
      const res = await api.post<{ response: string; status: string }>(
        `agents/${id}/test`,
      );
      setTestResult({
        ...testResult,
        [id]: { ok: true, message: res.response.slice(0, 200) },
      });
    } catch (err) {
      setTestResult({
        ...testResult,
        [id]: {
          ok: false,
          message: err instanceof ApiError ? err.detail : "Test failed",
        },
      });
    } finally {
      setTesting(null);
    }
  };

  return (
    <AppShell title="Agents" subtitle={`${agents.length} configured`}>
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="w-full px-panel-padding py-8 space-y-6">
          {error && (
            <div className="bg-error/10 border border-error/20 text-error rounded-lg p-3 flex items-center gap-2">
              <Icon name="error" filled />
              <span className="text-body-md">{error}</span>
            </div>
          )}

          {isLoading && <Loading size="lg" label="Loading agents..." />}

          {!isLoading && agents.length === 0 && (
            <EmptyState
              icon="smart_toy"
              title="No agents configured"
              description="Add agent definitions to backend/config/agents.yaml to get started."
            />
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {agents.map((a) => (
              <div
                key={a.id}
                className="bg-surface border border-border rounded-xl p-5 hover:border-primary/40 transition-colors"
              >
                <div className="flex items-start gap-3 mb-3">
                  <div className="w-10 h-10 rounded-lg bg-primary-fixed text-primary flex items-center justify-center flex-shrink-0">
                    <Icon name="smart_toy" filled className="text-[22px]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-body-lg font-bold text-on-surface">
                      {a.name}
                    </h3>
                    <p className="text-body-sm text-on-surface-variant">
                      {a.role}
                    </p>
                  </div>
                  <Pill variant="info" size="sm">
                    {a.llm_provider}
                  </Pill>
                </div>
                <p className="text-body-md text-on-surface-variant mb-4 leading-relaxed">
                  {a.description}
                </p>
                <div className="flex flex-wrap items-center gap-1.5 mb-4">
                  <Pill size="sm">
                    <Icon name="memory" className="text-[12px]" />
                    {a.memory_strategy} · {a.memory_limit}
                  </Pill>
                  <Pill size="sm">
                    <Icon name="model_training" className="text-[12px]" />
                    {a.llm_model}
                  </Pill>
                  {a.tools.map((t) => (
                    <Pill key={t} variant="primary" size="sm">
                      {t}
                    </Pill>
                  ))}
                </div>

                {testResult[a.id] && (
                  <div
                    className={[
                      "rounded-lg p-3 mb-3 text-body-sm",
                      testResult[a.id].ok
                        ? "bg-success/10 border border-success/20 text-success"
                        : "bg-error/10 border border-error/20 text-error",
                    ].join(" ")}
                  >
                    <div className="flex items-start gap-2">
                      <Icon
                        name={testResult[a.id].ok ? "check_circle" : "error"}
                        filled
                        className="text-[16px] mt-0.5"
                      />
                      <span className="font-mono">{testResult[a.id].message}</span>
                    </div>
                  </div>
                )}

                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => onTest(a.id)}
                    disabled={testing === a.id}
                    className="px-3 py-1.5 text-body-sm font-medium border border-border text-on-surface-variant hover:bg-surface-container-low rounded-lg disabled:opacity-50 flex items-center gap-1"
                  >
                    {testing === a.id ? (
                      <Loading size="sm" />
                    ) : (
                      <Icon name="science" className="text-[16px]" />
                    )}
                    Test
                  </button>
                  <a
                    href={`/chat?agent=${a.id}`}
                    className="px-3 py-1.5 bg-primary text-on-primary rounded-lg text-body-sm font-bold hover:opacity-90 flex items-center gap-1"
                  >
                    <Icon name="chat" className="text-[16px]" />
                    Chat
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
