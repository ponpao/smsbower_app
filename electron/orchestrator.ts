// Job Orchestrator: manages the batch queue and a pool of Python DSP worker
// processes (one child per "Thread", 1..8). Each worker speaks newline-delimited
// JSON over stdio. The orchestrator routes requests, fans out queued jobs across
// idle workers, and streams progress/status/result events to the renderer.

import { ChildProcessWithoutNullStreams, spawn } from 'node:child_process';
import { EventEmitter } from 'node:events';
import readline from 'node:readline';
import { resolvePythonEnv } from './pythonEnv.js';

interface Pending {
  resolve: (v: any) => void;
  reject: (e: any) => void;
  onProgress?: (stage: string, frac: number) => void;
}

// A single long-lived Python worker process.
class Worker {
  private proc: ChildProcessWithoutNullStreams;
  private rl: readline.Interface;
  private nextId = 1;
  private pending = new Map<number, Pending>();
  busy = false;
  ready = false;

  constructor(private onCrash: (w: Worker, err: string) => void) {
    const env = resolvePythonEnv();
    this.proc = spawn(env.python, env.args, {
      cwd: env.cwd,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
    }) as ChildProcessWithoutNullStreams;

    this.rl = readline.createInterface({ input: this.proc.stdout });
    this.rl.on('line', (line) => this.onLine(line));

    let stderrBuf = '';
    this.proc.stderr.on('data', (d) => { stderrBuf += d.toString(); });
    this.proc.on('exit', (code) => {
      const err = `worker exited (code ${code})\n${stderrBuf.slice(-2000)}`;
      for (const [, p] of this.pending) p.reject(new Error(err));
      this.pending.clear();
      this.onCrash(this, err);
    });
  }

  private onLine(line: string) {
    let msg: any;
    try { msg = JSON.parse(line); } catch { return; }
    const id = msg.id as number;
    const p = this.pending.get(id);
    if (!p) return;
    if (msg.event === 'progress') {
      p.onProgress?.(msg.stage, msg.frac);
      return;
    }
    this.pending.delete(id);
    this.busy = false;
    if (msg.error) p.reject(new Error(msg.error.message || 'worker error'));
    else p.resolve(msg.result);
  }

  request(method: string, params: any, onProgress?: (s: string, f: number) => void): Promise<any> {
    const id = this.nextId++;
    this.busy = true;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, onProgress });
      this.proc.stdin.write(JSON.stringify({ id, method, params }) + '\n');
    });
  }

  async ping(): Promise<void> {
    await this.request('ping', {});
    this.ready = true;
  }

  kill() {
    try { this.proc.kill(); } catch { /* ignore */ }
  }
}

export interface QueueJob {
  id: string;
  method: 'process' | 'merge_process';
  params: any;
}

type StatusFn = (jobId: string, status: string, extra?: any) => void;
type ProgressFn = (jobId: string, stage: string, frac: number) => void;
type ResultFn = (jobId: string, result: any) => void;

export class Orchestrator extends EventEmitter {
  private workers: Worker[] = [];
  private threads = 4;
  private queue: QueueJob[] = [];
  private running = false;
  private stopping = false;
  private activeCount = 0;

  onStatus: StatusFn = () => {};
  onProgress: ProgressFn = () => {};
  onResult: ResultFn = () => {};

  setThreads(n: number) {
    this.threads = Math.max(1, Math.min(8, n | 0));
  }

  // One-off request on a transient worker (analyze / authenticity / etc.).
  async oneShot(method: string, params: any): Promise<any> {
    const w = new Worker(() => {});
    try {
      await w.ping();
      return await w.request(method, params);
    } finally {
      w.kill();
    }
  }

  enqueue(jobs: QueueJob[]) {
    this.queue.push(...jobs);
    for (const j of jobs) this.onStatus(j.id, 'Queued');
  }

  stop() {
    this.stopping = true;
    this.queue = [];
  }

  isRunning() {
    return this.running;
  }

  async start() {
    if (this.running) return;
    this.running = true;
    this.stopping = false;

    // Spin up a worker pool sized to the thread setting.
    const pool: Worker[] = [];
    for (let i = 0; i < this.threads; i++) {
      pool.push(new Worker(() => {}));
    }
    await Promise.all(pool.map((w) => w.ping().catch(() => {})));
    this.workers = pool.filter((w) => w.ready);

    if (this.workers.length === 0) {
      this.running = false;
      throw new Error('No Python worker could start. Check the bundled runtime.');
    }

    await this.drain();

    this.workers.forEach((w) => w.kill());
    this.workers = [];
    this.running = false;
  }

  private drain(): Promise<void> {
    return new Promise((resolve) => {
      const pump = () => {
        if (this.stopping && this.activeCount === 0) return resolve();
        if (this.queue.length === 0 && this.activeCount === 0) return resolve();

        for (const w of this.workers) {
          if (w.busy || this.stopping) continue;
          const job = this.queue.shift();
          if (!job) break;
          this.activeCount++;
          this.onStatus(job.id, 'Processing');
          w
            .request(job.method, job.params, (stage, frac) =>
              this.onProgress(job.id, stage, frac),
            )
            .then((result) => {
              this.onStatus(job.id, 'Done', result);
              this.onResult(job.id, result);
            })
            .catch((err) => {
              this.onStatus(job.id, 'Error', { error: String(err?.message || err) });
              this.onResult(job.id, { error: String(err?.message || err) });
            })
            .finally(() => {
              this.activeCount--;
              pump();
            });
        }
      };
      // Kick and then re-pump whenever a worker frees up.
      const interval = setInterval(() => {
        if (!this.running || (this.queue.length === 0 && this.activeCount === 0)) {
          clearInterval(interval);
          return resolve();
        }
        pump();
      }, 50);
      pump();
    });
  }
}
