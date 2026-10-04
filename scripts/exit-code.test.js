// Run with: node --test scripts/
const test = require("node:test");
const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");
const { resolveExitCode } = require("./exit-code.js");

test("a numeric exit code is passed through unchanged", () => {
  assert.equal(resolveExitCode(0, null), 0);
  assert.equal(resolveExitCode(1, null), 1);
  assert.equal(resolveExitCode(7, null), 7);
});

test("a child killed by a signal is never reported as success", () => {
  assert.notEqual(resolveExitCode(null, "SIGTERM"), 0);
  assert.equal(resolveExitCode(null, "SIGTERM"), 128 + 15);
  assert.equal(resolveExitCode(null, "SIGKILL"), 128 + 9);
});

test("no code and no known signal is a failure, not a success", () => {
  assert.equal(resolveExitCode(null, null), 1);
  assert.equal(resolveExitCode(undefined, undefined), 1);
  assert.equal(resolveExitCode(null, "NOT_A_SIGNAL"), 1);
});

const root = path.resolve(__dirname, "..");
const venv = path.join(root, ".venv", process.platform === "win32" ? "Scripts" : "bin");
// run-python.js uses the repo .venv when present, otherwise `python` from PATH (as in CI).
const hasPython =
  fs.existsSync(path.join(venv, process.platform === "win32" ? "python.exe" : "python")) ||
  spawnSync("python", ["--version"], { stdio: "ignore" }).status === 0;

test("run-python.js propagates a failing exit code", { skip: !hasPython && "no .venv python" }, () => {
  const result = spawnSync(process.execPath, [path.join(__dirname, "run-python.js"), "-c", "raise SystemExit(7)"], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  assert.equal(result.status, 7);
});

test("run-python.js propagates a failing assertion as non-zero", { skip: !hasPython && "no .venv python" }, () => {
  const result = spawnSync(process.execPath, [path.join(__dirname, "run-python.js"), "-c", "assert 1 == 2"], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  assert.notEqual(result.status, 0);
});
