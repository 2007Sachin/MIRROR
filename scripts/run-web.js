const { spawn } = require("child_process");
const path = require("path");
const { loadEnvConfig } = require("@next/env");

const projectRoot = path.resolve(__dirname, "..");
const command = process.argv[2];

if (!command) {
  throw new Error("Usage: node scripts/run-web.js <dev|build>");
}

loadEnvConfig(projectRoot, process.env.NODE_ENV !== "production");

const child = spawn("npm", ["--workspace", "@mirror/web", "run", command], {
  cwd: projectRoot,
  env: process.env,
  shell: process.platform === "win32",
  stdio: "inherit",
});

child.on("exit", (code) => process.exit(code ?? 0));
