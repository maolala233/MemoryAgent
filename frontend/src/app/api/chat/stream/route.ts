import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND_URL =
  process.env.BACKEND_URL || "http://localhost:8000";

/**
 * SSE 流式代理路由。
 *
 * Next.js rewrites() 底层使用 http-proxy，会缓冲整个响应体，
 * 导致 text/event-stream 流式数据无法实时推送到浏览器，
 * 最终代理层超时返回 HTTP 500。
 *
 * 此 Route Handler 手动建立到后端的连接，并以 ReadableStream
 * 方式逐块转发，确保 SSE 实时性。
 */
export async function POST(req: NextRequest) {
  const body = await req.text();

  const upstream = await fetch(`${BACKEND_URL}/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body,
  });

  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text().catch(() => "");
    return new Response(text || `Upstream error: ${upstream.status}`, {
      status: upstream.status,
      headers: { "Content-Type": "text/plain" },
    });
  }

  // 将后端 ReadableStream 逐块透传给浏览器
  const stream = new ReadableStream({
    async start(controller) {
      const reader = upstream.body!.getReader();
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          controller.enqueue(value);
        }
      } catch (err) {
        controller.error(err);
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
