// Resolves the SYSTEM browser for playwright-core. Nothing is ever downloaded.
import fs from "node:fs";

const WINDOWS_CANDIDATES = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
];

/** Returns playwright `launch()` options: MIRROR_QA_BROWSER, then known Windows paths, else channel "chrome" (Linux/CI). */
export function resolveBrowser(env = process.env) {
  const override = env.MIRROR_QA_BROWSER;
  if (override) {
    if (!fs.existsSync(override)) throw new Error(`MIRROR_QA_BROWSER points to a missing file: ${override}`);
    return { executablePath: override, describe: override };
  }
  if (process.platform === "win32") {
    const found = WINDOWS_CANDIDATES.find((candidate) => fs.existsSync(candidate));
    if (found) return { executablePath: found, describe: found };
    throw new Error(`No system Chrome/Edge found (looked in ${WINDOWS_CANDIDATES.join(", ")}); set MIRROR_QA_BROWSER.`);
  }
  return { channel: "chrome", describe: 'channel "chrome"' };
}
