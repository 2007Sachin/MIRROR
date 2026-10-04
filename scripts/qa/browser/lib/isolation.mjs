// Approved execution environments for the browser critical path.
//
// There is exactly one: an ephemeral GitHub-hosted Actions runner with NO secrets. Isolation is
// provided by that environment (fresh VM per run, secret-free checkout, no .env files, no provider or
// hosted-database credentials in the process environment) and is *verified here*, not merely asserted:
// every condition below must hold or execution is refused. Nothing in the browser path is given a
// credential, so there is nothing to leak or to mutate on a hosted service even if a request escaped.
// A developer machine (or any other host) is never an approved environment.
import fs from 'node:fs';
import path from 'node:path';

const CREDENTIAL_ENV = [
  'SUPABASE_SERVICE_ROLE_KEY', 'SARVAM_API_KEY', 'DEEPGRAM_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY',
  'GEMINI_API_KEY', 'GOOGLE_API_KEY', 'AZURE_OPENAI_API_KEY', 'SUPABASE_ACCESS_TOKEN', 'DATABASE_URL',
];
const REPOSITORY_ROOT = path.resolve(new URL('../../../..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'));

export function ephemeralRunnerViolations({ env = process.env, root = REPOSITORY_ROOT, exists = fs.existsSync, list = fs.readdirSync } = {}) {
  const problems = [];
  if (env.MIRROR_QA_GITHUB_HOSTED !== '1') problems.push('MIRROR_QA_GITHUB_HOSTED=1 was not set by the CI job');
  if (env.GITHUB_ACTIONS !== 'true') problems.push('not running inside GitHub Actions');
  if (env.RUNNER_ENVIRONMENT !== 'github-hosted') problems.push('runner is not GitHub-hosted (RUNNER_ENVIRONMENT)');
  for (const name of CREDENTIAL_ENV) if (env[name]) problems.push(`credential variable present in environment: ${name}`);
  for (const name of Object.keys(env)) {
    if (/^NEXT_PUBLIC_SUPABASE_URL$/.test(name) && env[name] && !/^http:\/\/127\.0\.0\.1:\d+$/.test(env[name])) problems.push('NEXT_PUBLIC_SUPABASE_URL is not a loopback origin');
    if (/^NEXT_PUBLIC_API_URL$/.test(name) && env[name] && !/^http:\/\/127\.0\.0\.1:\d+$/.test(env[name])) problems.push('NEXT_PUBLIC_API_URL is not a loopback origin');
  }
  for (const dir of [root, path.join(root, 'apps', 'web'), path.join(root, 'apps', 'api')]) {
    let names = [];
    try { names = list(dir); } catch { /* directory absent is fine */ }
    for (const name of names) if (/^\.env(\..*)?$/.test(name) && name !== '.env.example') problems.push(`dotenv file present: ${path.relative(root, path.join(dir, name)) || name}`);
  }
  return problems;
}

export function requireEphemeralRunner(options) {
  const problems = ephemeralRunnerViolations(options);
  if (problems.length) throw new Error(`BLOCKED: SSR and build egress isolation is only provided by an approved ephemeral GitHub-hosted runner; ${problems.join('; ')}. Browser/build execution is disabled here; see SAFETY.md.`);
}
