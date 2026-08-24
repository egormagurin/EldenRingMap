'use strict';
/**
 * Optional live-memory bridge.
 *
 * Spawns tools/live_memory.py, which reads the running game's player position
 * read-only, and relays each sample to the browser.
 *
 * Strictly additive. If Python is missing, the game is closed, we lack admin
 * rights, or the byte signatures stop matching after a game patch, this logs
 * once and the map carries on working from the save file alone.
 */
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

class LiveMemory {
  constructor({ root, python = 'python', hz = 20, onPos, onStatus }) {
    this.root = root;
    this.python = python;
    this.hz = hz;
    this.onPos = onPos || (() => {});
    this.onStatus = onStatus || (() => {});
    this.enabled = false;
    this.status = 'off';
    this.detail = null;
    this.pos = null;
    this.child = null;
  }

  get state() {
    return { enabled: this.enabled, status: this.status, detail: this.detail };
  }

  start() {
    const script = path.join(this.root, 'tools', 'live_memory.py');
    if (!fs.existsSync(script)) {
      console.error('[live] tools/live_memory.py is missing - live mode disabled');
      return;
    }
    this.enabled = true;
    this._setStatus('starting');

    try {
      this.child = spawn(this.python, [script, '--hz', String(this.hz)], {
        cwd: this.root,
        stdio: ['ignore', 'pipe', 'pipe'],
      });
    } catch (err) {
      console.error(`[live] could not start "${this.python}": ${err.message}`);
      this._setStatus('error', err.message);
      return;
    }

    let buf = '';
    this.child.stdout.setEncoding('utf8');
    this.child.stdout.on('data', (chunk) => {
      buf += chunk;
      let nl;
      while ((nl = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (line) this._handle(line);
      }
    });

    this.child.stderr.setEncoding('utf8');
    this.child.stderr.on('data', (d) => {
      const first = String(d).trim().split('\n')[0];
      if (first) console.error('[live] ' + first);
    });

    this.child.on('error', (err) => {
      console.error(`[live] ${err.message}`);
      this._setStatus('error', err.message);
    });

    this.child.on('exit', (code) => {
      this.child = null;
      console.error(`[live] reader exited (code ${code}) - continuing from the save file`);
      this._setStatus('stopped', `reader exited (${code})`);
    });

    const kill = () => this.stop();
    process.on('exit', kill);
    process.on('SIGINT', () => { kill(); process.exit(0); });
    process.on('SIGTERM', () => { kill(); process.exit(0); });
  }

  _handle(line) {
    let msg;
    try { msg = JSON.parse(line); } catch { return; }
    if (msg.type === 'pos') {
      this.pos = msg;
      if (this.status !== 'live') this._setStatus('live');
      this.onPos(msg);
    } else if (msg.type === 'status') {
      console.log(`[live] ${msg.state}${msg.detail ? ': ' + msg.detail : ''}` +
                  (msg.pid ? ` (pid ${msg.pid})` : ''));
      this._setStatus(msg.state, msg.detail || null);
    }
  }

  _setStatus(status, detail = null) {
    this.status = status;
    this.detail = detail;
    this.onStatus(this.state);
  }

  stop() {
    if (this.child) {
      try { this.child.kill(); } catch { /* already gone */ }
      this.child = null;
    }
  }
}

module.exports = { LiveMemory };
