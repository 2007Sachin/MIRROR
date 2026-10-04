const { spawn } = require("child_process");
const { resolveExitCode } = require("./exit-code");
const path = require("path");

const projectRoot = path.resolve(__dirname, "..");
const apiPath = path.join(projectRoot, "apps", "api");
const existingPythonPath = process.env.PYTHONPATH;
const pythonPath = existingPythonPath
  ? `${apiPath}${path.delimiter}${existingPythonPath}`
  : apiPath;

const child = spawn(
  process.execPath,
  [
    path.join(projectRoot, "scripts", "run-python.js"),
    path.join(projectRoot, "workers", "assessor", "worker.py"),
    ...process.argv.slice(2),
  ],
  {
    cwd: projectRoot,
    env: { ...process.env, PYTHONPATH: pythonPath },
    shell: false,
    stdio: "inherit",
  },
);

child.on("exit", (code, signal) => process.exit(resolveExitCode(code, signal)));
