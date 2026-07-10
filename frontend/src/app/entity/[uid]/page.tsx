"use client";
import { useEffect, useState, use } from "react";
import { Icon } from "@/components/shared/Icon";
import { useMandol } from "@/hooks/useMandol";

interface MemoryUnit {
  uid: string;
  text: string;
  raw_data: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

interface Edge {
  source: string;
  target: string;
  relation: string;
}

interface DetailResponse {
  unit: MemoryUnit;
  edges: Edge[];
}

export default function EntityDetailPage({ params }: { params: Promise<{ uid: string }> }) {
  const { uid } = use(params);
  const decodedUid = decodeURIComponent(uid);
  const mandol = useMandol();
  const [data, setData] = useState<DetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const res = await mandol.getEntityDetail(decodedUid);
        if (!cancelled) setData(res);
      } catch (err: unknown) {
        const detail =
          (err as { response?: { data?: { detail?: string } }; message?: string })
            ?.response?.data?.detail ||
          (err as { message?: string })?.message ||
          "加载失败";
        if (!cancelled) setError(detail);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [decodedUid, mandol]);

  const unit = data?.unit;
  const rd = (unit?.raw_data || {}) as Record<string, unknown>;
  const meta = (unit?.metadata || {}) as Record<string, unknown>;
  const kind = (meta?.type as string) || "entity";
  const name = (rd.entity_name as string) || (rd.event_title as string) || (unit?.text || "").split("\n")[0] || decodedUid;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <a href="/graph" className="text-on-surface-variant hover:text-primary">
          <Icon name="arrow_back" />
        </a>
        <h1 className="text-h4 font-semibold text-on-surface">实体/事件详情</h1>
        {kind && (
          <span className="ml-2 text-body-sm px-2 py-0.5 rounded-full bg-primary-container text-on-primary-container">
            {kind}
          </span>
        )}
      </div>

      {loading && (
        <div className="bg-surface border border-border rounded-xl p-8 text-center text-on-surface-variant">
          加载中…
        </div>
      )}

      {error && (
        <div className="bg-error-container text-on-error-container rounded-xl p-6">
          <p className="font-semibold mb-1">加载失败</p>
          <p className="text-body-sm">{error}</p>
        </div>
      )}

      {!loading && !error && data && (
        <>
          <section className="bg-surface border border-border rounded-xl p-6 space-y-3">
            <h2 className="text-h5 font-semibold text-on-surface">{name}</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-body-sm">
              <Field label="UID" value={unit?.uid || decodedUid} mono />
              <Field label="来源文档" value={(meta?.source_doc as string) || "—"} />
              <Field label="项目 ID" value={(meta?.project_id as string) || "—"} />
              <Field label="类型" value={(rd.entity_type as string) || (rd.event_time ? "Event" : "—")} />
            </div>
            {Boolean(rd.entity_description || rd.event_description) && (
              <div className="mt-3">
                <h3 className="text-body-sm font-semibold text-on-surface-variant mb-1">描述</h3>
                <p className="text-body text-on-surface whitespace-pre-wrap">
                  {(rd.entity_description as string) || (rd.event_description as string)}
                </p>
              </div>
            )}
            {unit?.text && (
              <div className="mt-3">
                <h3 className="text-body-sm font-semibold text-on-surface-variant mb-1">原文</h3>
                <pre className="text-body-sm bg-surface-variant/40 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">
                  {unit.text}
                </pre>
              </div>
            )}
          </section>

          <section className="bg-surface border border-border rounded-xl p-6 space-y-3">
            <h2 className="text-h5 font-semibold text-on-surface">关联</h2>
            {(data.edges || []).length === 0 ? (
              <p className="text-body-sm text-on-surface-variant">暂无关联</p>
            ) : (
              <ul className="space-y-2">
                {data.edges.map((e, i) => (
                  <li
                    key={i}
                    className="flex items-center gap-2 text-body-sm bg-surface-variant/30 rounded-lg px-3 py-2"
                  >
                    <a
                      href={`/entity/${encodeURIComponent(e.source)}`}
                      className="text-primary hover:underline"
                    >
                      {shortName(e.source)}
                    </a>
                    <span className="text-on-surface-variant">— {e.relation || "RELATED"} →</span>
                    <a
                      href={`/entity/${encodeURIComponent(e.target)}`}
                      className="text-primary hover:underline"
                    >
                      {shortName(e.target)}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function shortName(uid: string) {
  const parts = uid.split(":");
  return parts[parts.length - 1] || uid;
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="text-body-sm text-on-surface-variant">{label}</div>
      <div className={`mt-0.5 ${mono ? "font-mono text-body-sm" : "text-body"} text-on-surface break-all`}>
        {value}
      </div>
    </div>
  );
}
