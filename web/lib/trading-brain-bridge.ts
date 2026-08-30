/**
 * WS-4 Trading Brain Ledger Bridge (shared helper).
 *
 * Bridges Next.js API routes to the canonical Trading Brain ledger through the
 * python web bridge (`scripts/trading_brain/web_bridge.py`). The bridge is the
 * ONLY access path: compliance logic (fail-closed rules, RISK_UNASSESSABLE,
 * custody tokens) lives server-side in python and is never reimplemented here.
 */

import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execFileAsync = promisify(execFile);

const REPO_ROOT = path.resolve(process.cwd(), '..');
const PYTHON = process.env.TRADING_BRAIN_PYTHON ?? path.join(REPO_ROOT, '.venv', 'Scripts', 'python.exe');

export async function runBridgeHandler(
  handler: string,
  args: Record<string, string | boolean | undefined | null>
): Promise<Record<string, unknown>> {
  const cliArgs = ['-m', 'scripts.trading_brain.web_bridge', handler];
  for (const [key, value] of Object.entries(args)) {
    if (value === undefined || value === null || value === false) continue;
    const flag = key.replaceAll('_', '-');
    // true renders a bare store_true argparse flag (--synthetic); strings pair up.
    if (value === true) {
      cliArgs.push(`--${flag}`);
    } else {
      cliArgs.push(`--${flag}`, String(value));
    }
  }
  try {
    const { stdout } = await execFileAsync(PYTHON, cliArgs, {
      cwd: REPO_ROOT,
      timeout: 60_000,
      maxBuffer: 32 * 1024 * 1024,
      windowsHide: true,
    });
    const trimmed = stdout.trim();
    if (!trimmed) throw new Error(`bridge handler '${handler}' produced no output`);
    return JSON.parse(trimmed);
  } catch (err) {
    // execFile failures carry the child process's stdout/stderr on the error object.
    // The bridge prints single-line JSON ({...}) to stdout even on failure; the
    // err.message alone would only contain the command string and exit code, so the
    // structured bridge error MUST be extracted from err.stdout first.
    const execErr = err as { stdout?: string; stderr?: string; message?: string };
    const candidates = [execErr.stdout, execErr.stderr, execErr.message];
    for (const source of candidates) {
      if (!source) continue;
      const text = source.trim();
      if (!text.startsWith('{')) continue;
      try {
        const parsed = JSON.parse(text) as Record<string, unknown>;
        if (parsed && typeof parsed === 'object' && 'error' in parsed) return parsed;
      } catch {
        /* try next source */
      }
    }
    throw new Error(`web_bridge ${handler} failed: ${execErr.message ?? String(err)}`);
  }
}