import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Version shown at the bottom of every page: the VERSION file + the commit being built
// (Cloudflare Pages sets CF_PAGES_COMMIT_SHA; locally we ask git).
const version = readFileSync(new URL("../../VERSION", import.meta.url), "utf8").trim();
let commit = (process.env.CF_PAGES_COMMIT_SHA ?? "").slice(0, 7);
if (!commit) {
  try { commit = execSync("git rev-parse --short HEAD").toString().trim(); } catch { commit = "dev"; }
}

// In development, /api calls are forwarded to the API on port 8000.
export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(version),
    __APP_COMMIT__: JSON.stringify(commit),
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
