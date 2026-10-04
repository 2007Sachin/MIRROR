// Fail-closed browser QA entry. No supported SSR/build isolation adapter exists.
// Do not restore build/start code until SAFETY.md requirements are verified.
import { parseArgs, requireSupportedIsolation } from './lib/safety.mjs';

try {
  parseArgs(process.argv.slice(2));
  requireSupportedIsolation();
} catch (error) {
  console.error(`run.mjs: ${error.message}`);
  process.exitCode = 1;
}
