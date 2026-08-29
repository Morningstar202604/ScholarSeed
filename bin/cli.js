#!/usr/bin/env node
/**
 * scholarseed CLI launcher.
 *
 * The ScholarSeed engine is pure Python (stdlib-only, 3.9+). This shim lets
 * npm-based users run the exact same CLI:
 *
 *   scholarseed proofread paper.md --genre empirical
 *   scholarseed verify-refs thesis.md --fail-on C
 *
 * Requires Python 3.9+ on PATH (override with the PYTHON env var).
 */
"use strict";

const { spawn } = require("child_process");
const path = require("path");

const py = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
const cli = path.join(__dirname, "..", "scripts", "cli.py");
const args = process.argv.slice(2);

const child = spawn(py, [cli, ...args], { stdio: "inherit" });

child.on("error", (err) => {
  if (err.code === "ENOENT") {
    console.error(
      `[scholarseed] Python interpreter "${py}" not found on PATH.\n` +
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
