// Shared exit-code mapping for the npm wrapper scripts (run-python, run-web, run-assessor).
//
// A child that is killed by a signal reports `code === null`. Mapping that to 0 would turn a
// crashed or killed test run into a green one, so a missing code is always a failure.
const os = require("node:os");

function resolveExitCode(code, signal) {
  if (typeof code === "number") return code;
  const number = signal ? os.constants.signals[signal] : undefined;
  return typeof number === "number" ? 128 + number : 1;
}

module.exports = { resolveExitCode };
