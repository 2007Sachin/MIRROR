const { execSync } = require('child_process');

function freePort(port) {
  try {
    if (process.platform === 'win32') {
      const output = execSync(`netstat -ano`, { encoding: 'utf8', stdio: ['pipe', 'pipe', 'ignore'] });
      const lines = output.trim().split('\n');
      const pids = new Set();
      for (const line of lines) {
        if (!line.includes(`:${port}`)) continue;
        const parts = line.trim().split(/\s+/);
        if (parts.length >= 5) {
          const localAddr = parts[1];
          const state = parts[3];
          const pid = parts[parts.length - 1];
          if (localAddr && (localAddr.endsWith(`:${port}`) || localAddr.includes(`:${port} `)) && state === 'LISTENING' && pid && pid !== '0') {
            pids.add(pid);
          }
        }
      }
      for (const pid of pids) {
        try {
          execSync(`taskkill /F /PID ${pid}`, { stdio: 'ignore' });
          console.log(`[predev] Cleared stale process PID ${pid} on port ${port}`);
        } catch {
          // Ignore if already terminated
        }
      }
    } else {
      const pids = execSync(`lsof -t -i:${port}`, { encoding: 'utf8', stdio: ['pipe', 'pipe', 'ignore'] }).trim();
      if (pids) {
        const pidList = pids.split(/\s+/).join(' ');
        execSync(`kill -9 ${pidList}`, { stdio: 'ignore' });
        console.log(`[predev] Cleared stale process PID(s) ${pidList} on port ${port}`);
      }
    }
  } catch {
    // Port is free or lookup command produced no matches
  }
}

freePort(3000);
freePort(8000);
