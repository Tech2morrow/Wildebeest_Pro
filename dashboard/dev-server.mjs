#!/usr/bin/env node
import { createServer } from "node:http";
import { readFile, realpath, stat } from "node:fs/promises";
import { extname, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const dashboardRoot = resolve(root, "dashboard");
const assetsRoot = resolve(root, "assets");
const port = Number(process.env.PORT || 8088);
const types = { ".html":"text/html; charset=utf-8", ".css":"text/css; charset=utf-8", ".js":"text/javascript; charset=utf-8", ".mjs":"text/javascript; charset=utf-8", ".svg":"image/svg+xml", ".png":"image/png" };

function requestedFile(pathname) {
  if (pathname === "/") return { base: dashboardRoot, target: resolve(dashboardRoot, "index.html") };
  const route = pathname.startsWith("/dashboard/") ? [dashboardRoot, pathname.slice(11)]
    : pathname.startsWith("/assets/") ? [assetsRoot, pathname.slice(8)] : null;
  if (!route || route[1].split("/").some((part) => !part || part.startsWith("."))) throw new Error("route not allowed");
  const target = resolve(route[0], route[1]);
  const rel = relative(route[0], target);
  if (rel.startsWith("..") || rel.includes(`..${sep}`)) throw new Error("outside web root");
  return { base: route[0], target };
}

createServer(async (request, response) => {
  try {
    if (!['GET', 'HEAD'].includes(request.method || 'GET')) throw new Error("method not allowed");
    const pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
    const requested = requestedFile(pathname);
    const target = await realpath(requested.target);
    if (target !== requested.base && !target.startsWith(`${requested.base}${sep}`)) throw new Error("symlink outside web root");
    if (!(await stat(target)).isFile() || !types[extname(target).toLowerCase()]) throw new Error("not a public file");
    response.writeHead(200, { "Content-Type": types[extname(target).toLowerCase()] || "application/octet-stream", "Cache-Control":"no-store" });
    response.end(request.method === 'HEAD' ? undefined : await readFile(target));
  } catch { response.writeHead(404, {"Content-Type":"text/plain"}); response.end("Not found\n"); }
}).listen(port, "127.0.0.1", () => console.log(`Wildebeest dashboard: http://127.0.0.1:${port}/`));
