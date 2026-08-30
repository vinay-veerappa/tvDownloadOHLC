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
  args: Record<string, string | undefined>
): Promise<Record<string, unknown>> {
  const cliArgs = ['-m', 'scripts.trading_brain.web_bridge', handler];
  for (const [key, value] of Object.entries(args)) {
    if (value === undefined || value === null) continue;
    const flag = key.replaceAll('_', '-');
    cliArgs.push(`--${flag}`, String(value));
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
    const message = err instanceof Error ? err.message : String(err);
    // The bridge prints single-line JSON errors on failure; surface them.
    const start = message.indexOf('{');
    if (start >= 0) {
      try {
        return JSON.parse(message.slice(start));
      } catch {
        /* fall through */
      }
    }
    throw new Error(`web_bridge ${handler} failed: ${message}`);
  }
}