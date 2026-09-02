const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const projectRoot = path.resolve(__dirname, '..');
const venvWin = path.join(projectRoot, '.venv', 'Scripts', 'python.exe');
const venvPosix = path.join(projectRoot, '.venv', 'bin', 'python');

let pythonExe = 'python';
if (process.platform === 'win32' && fs.existsSync(venvWin)) {
  pythonExe = venvWin;
} else if (fs.existsSync(venvPosix)) {
  pythonExe = venvPosix;
} else if (fs.existsSync(venvWin)) {
  pythonExe = venvWin;
}

const args = process.argv.slice(2);
const child = spawn(pythonExe, args, { stdio: 'inherit', cwd: projectRoot, shell: false });

child.on('error', (err) => {
  console.error(`[run-python] Failed to start ${pythonExe}:`, err.message);
  process.exit(1);
});

child.on('exit', (code) => {
  process.exit(code ?? 0);
});
