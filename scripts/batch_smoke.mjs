// Headless integration smoke test for the Node <-> Python worker-pool path
// (the same protocol the orchestrator uses, without Electron). Spawns N workers,
// processes a folder of files in parallel, and verifies every job completes and
// hits the LUFS target within tolerance.
//
// Usage: node scripts/batch_smoke.mjs <inputDir> <outDir> [threads]

import { spawn } from 'node:child_process';
import readline from 'node:readline';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const python = path.join(root, '.venv', 'bin', 'python');
const pyCwd = path.join(root, 'python');

const inDir = process.argv[2] || '/tmp/tk/batch';
const outDir = process.argv[3] || '/tmp/tk/batch_out';
const THREADS = parseInt(process.argv[4] || '4', 10);
fs.mkdirSync(outDir, { recursive: true });

const files = fs.readdirSync(inDir).filter((f) => /\.(wav|flac|mp3|aiff?)$/i.test(f));

class Worker {
  constructor() {
    this.proc = spawn(python, ['-m', 'travkod.worker'], {
      cwd: pyCwd, env: { ...process.env, PYTHONUNBUFFERED: '1' },
    });
    this.rl = readline.createInterface({ input: this.proc.stdout });
    this.pending = new Map();
    this.id = 1;
    this.busy = false;
    this.rl.on('line', (line) => {
      let m; try { m = JSON.parse(line); } catch { return; }
      const p = this.pending.get(m.id);
      if (!p) return;
      if (m.event === 'progress') return;
      this.pending.delete(m.id);
      this.busy = false;
      m.error ? p.reject(new Error(m.error.message)) : p.resolve(m.result);
    });
    this.proc.stderr.on('data', (d) => process.stderr.write(d));
  }
  req(method, params) {
    const id = this.id++;
    this.busy = true;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.proc.stdin.write(JSON.stringify({ id, method, params }) + '\n');
    });
  }
  kill() { this.proc.kill(); }
}

const params = {
  strip: { de_ess: 40, clear: -2, saturation: 25, comp: 25, air: 8, limit: 85 },
  humanize: 40, lufs_target: -14, true_peak_ceiling: -1,
};

async function main() {
  const t0 = Date.now();
  const pool = Array.from({ length: THREADS }, () => new Worker());
  await Promise.all(pool.map((w) => w.req('ping', {})));

  const queue = files.map((f) => ({
    input: path.join(inDir, f),
    output: path.join(outDir, path.parse(f).name + '_travkod'),
    params, export: { format: 'wav', bit_depth: 24 },
  }));

  let done = 0, failed = 0;
  const results = [];
  async function run(w) {
    while (queue.length) {
      const job = queue.shift();
      try {
        const r = await w.req('process', job);
        results.push(r); done++;
        process.stdout.write(`  [${done}/${files.length}] ${path.basename(r.output_path)} -> ${r.metrics.loudness_lufs} LUFS, ${r.metrics.true_peak_dbtp} dBTP\n`);
      } catch (e) {
        failed++; console.error('  FAIL', e.message);
      }
    }
  }
  await Promise.all(pool.map((w) => run(w)));
  pool.forEach((w) => w.kill());

  const secs = ((Date.now() - t0) / 1000).toFixed(1);
  const offTarget = results.filter((r) => Math.abs((r.metrics.loudness_lufs ?? -99) + 14) > 0.5);
  const overPeak = results.filter((r) => (r.metrics.true_peak_dbtp ?? 0) > -1 + 1e-6);

  console.log(`\nProcessed ${done}/${files.length} files with ${THREADS} threads in ${secs}s (failed: ${failed})`);
  console.log(`LUFS off-target (>0.5 LU): ${offTarget.length}`);
  console.log(`True-peak over -1 dBTP: ${overPeak.length}`);

  const ok = done === files.length && failed === 0 && offTarget.length === 0 && overPeak.length === 0;
  console.log(ok ? '\nBATCH SMOKE: PASS' : '\nBATCH SMOKE: FAIL');
  process.exit(ok ? 0 : 1);
}

main().catch((e) => { console.error(e); process.exit(1); });
