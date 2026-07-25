import reportHtml from "../outputs/index.html?raw";

interface ExecutionContext {
  waitUntil(promise: Promise<unknown>): void;
  passThroughOnException(): void;
}

const REPORT_PATHS = new Set(["/", "/index.html", "/songyuan_security_daily.html"]);

const worker = {
  async fetch(request: Request, _env: unknown, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    if (!REPORT_PATHS.has(url.pathname)) {
      return new Response("Not Found", { status: 404 });
    }

    const headers = {
      "Cache-Control": "public, max-age=300",
      "Content-Type": "text/html; charset=utf-8",
    };
    if (request.method === "HEAD") {
      return new Response(null, { status: 200, headers });
    }
    if (request.method !== "GET") {
      return new Response("Method Not Allowed", {
        status: 405,
        headers: { Allow: "GET, HEAD" },
      });
    }
    return new Response(reportHtml, { status: 200, headers });
  },
};

export default worker;
