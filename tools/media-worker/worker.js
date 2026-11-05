// ConcertBuddy media gate: a Cloudflare Worker that serves your R2 bucket only to
// your own site's video, audio and image players.
//
// With the bucket's public r2.dev address switched off, this is the only way in.
// It turns away:
//   - opening a clip's address in a browser tab, or "Save link as…" / downloading it
//   - other websites embedding your clips or photos
//   - plain download tools (curl, wget) that don't pretend to be your site
// It can't stop someone determined (browser developer tools, or a tool that fakes the
// headers), any more than it can stop screen recording.
//
// Setup (Cloudflare dashboard, no tools needed): docs/hosting-media.md › "Stop easy downloads".
//   Binding:  MEDIA            -> your R2 bucket
//   Variable: ALLOWED_ORIGINS  -> comma-separated, e.g.
//             https://you.github.io/,http://localhost:8000/,http://127.0.0.1:8000/

const PLAYERS = new Set(["video", "audio", "image", "track"]); // Sec-Fetch-Dest values of media elements

function allowed(request, env) {
  // Where the request comes from: browsers send the page's address (or at least its origin)
  // as Referer when a <video>/<img> on that page loads a file. A tab, a download or curl don't.
  const from = request.headers.get("referer") || request.headers.get("origin") || "";
  const origins = (env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean)
    .map((o) => (o.endsWith("/") ? o : o + "/")); // so https://you.github.io.evil.example doesn't pass
  if (!origins.some((o) => (from + "/").startsWith(o))) return false; // an Origin header has no trailing slash
  // What it's for: a media element on the page, not a page of its own (opening the link in a tab).
  // Browsers too old to send Sec-Fetch-Dest are let through on the Referer check alone.
  const dest = request.headers.get("sec-fetch-dest");
  return !dest || PLAYERS.has(dest);
}

export default {
  async fetch(request, env) {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method not allowed", { status: 405, headers: { allow: "GET, HEAD" } });
    }
    if (!allowed(request, env)) {
      return new Response("Not available", { status: 403, headers: { "cache-control": "no-store" } });
    }
    const key = decodeURIComponent(new URL(request.url).pathname.slice(1));
    if (!key || key.endsWith("/")) return new Response("Not found", { status: 404 });

    // Byte ranges: browsers fetch video in pieces (and Safari insists on it).
    const ranged = request.headers.has("range");
    const object = request.method === "HEAD"
      ? await env.MEDIA.head(key)
      : await env.MEDIA.get(key, { range: request.headers, onlyIf: request.headers });
    if (object === null) return new Response("Not found", { status: 404 });

    const headers = new Headers();
    object.writeHttpMetadata(headers);
    headers.set("etag", object.httpEtag);
    headers.set("accept-ranges", "bytes");
    headers.set("cache-control", "private, max-age=86400"); // the viewer's browser may keep it a day; no shared caches
    headers.set("content-disposition", "inline");
    headers.set("vary", "Referer, Sec-Fetch-Dest");

    if (!("body" in object) || !object.body) { // HEAD, or a conditional request that matched (not modified)
      headers.set("content-length", String(object.size));
      return new Response(null, { status: request.method === "HEAD" ? 200 : 304, headers });
    }
    if (ranged && object.range) {
      const r = object.range;
      const offset = "suffix" in r ? object.size - r.suffix : r.offset ?? 0;
      const length = "suffix" in r ? r.suffix : r.length ?? object.size - offset;
      headers.set("content-range", `bytes ${offset}-${offset + length - 1}/${object.size}`);
      headers.set("content-length", String(length));
      return new Response(object.body, { status: 206, headers });
    }
    headers.set("content-length", String(object.size));
    return new Response(object.body, { status: 200, headers });
  },
};
