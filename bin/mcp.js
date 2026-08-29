#!/usr/bin/env node
/**
 * scholarseed-mcp launcher.
 *
 * The ScholarSeed MCP server is pure Python (stdlib-only, 3.9+) and speaks
 * JSON-RPC 2.0 over stdio. This shim exists so npm-based MCP clients can
 * spawn it the standard way:
 *
 *   npx scholarseed-mcp
 *
 * Requires Python 3.9+ on PATH (override with the PYTHON env var).
 */
"use strict";

const { spawn } = require("child_process");
const path = require("path");

const py = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
const server = path.join(__dirname, "..", "scripts", "paper_tools.py");

const child = spawn(py, [server], { stdio: "inherit" });

child.on("error", (err) => {
  if (err.code === "ENOENT") {
    console.error(
      `[scholarseed-mcp] Python interpreter "${py}" not found on PATH.\n` +
        `Install Python 3.9+ or set PYTHON=/path/to/python.`
    );
    process.exit(1);
  }
  throw err;
});

child.on("exit", (code) => process.exit(code == null ? 1 : code));

for (const sig of ["SIGINT", "SIGTERM"]) {
  process.on(sig, () => child.kill(sig));
}
