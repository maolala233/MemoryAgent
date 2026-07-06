// Lightweight API client for the Codex Memory backend.
// Uses /api/* rewrites defined in next.config.js so calls work in both
// dev (Next proxy -> backend) and production.

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

type Json = unknown;

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const url = endpoint.startsWith("http")
    ? endpoint
    : `/api/${endpoint.replace(/^\//, "")}`;
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (!(options.body instanceof FormData) && options.body) {
    headers["Content-Type"] = "application/json";
  }
  const resp = await fetch(url, { ...options, headers });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const data = await resp.json();
      detail = data.detail || data.message || JSON.stringify(data);
    } catch {
      // ignore parse errors
    }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  const ct = resp.headers.get("content-type") || "";
  if (!ct.includes("application/json")) return (await resp.text()) as unknown as T;
  return (await resp.json()) as T;
}

export const api = {
  get: <T>(endpoint: string) => request<T>(endpoint, { method: "GET" }),
  post: <T>(endpoint: string, body?: Json | FormData) =>
    request<T>(endpoint, {
      method: "POST",
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
    }),
  put: <T>(endpoint: string, body?: Json) =>
    request<T>(endpoint, {
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
    }),
  del: <T>(endpoint: string) => request<T>(endpoint, { method: "DELETE" }),
};

export function wsUrl(path: string): string {
  const origin =
    typeof window !== "undefined" ? window.location.origin : "";
  // In dev the Next proxy covers /api, but websockets need direct backend.
  const backend =
    process.env.NEXT_PUBLIC_BACKEND_WS ||
    (origin ? `${origin.replace(/^http/, "ws")}` : "ws://localhost:8000");
  return `${backend}${path.startsWith("/") ? path : `/${path}`}`;
}
