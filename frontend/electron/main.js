const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');

let mainWindow = null;
let backendReady = false;

const BACKEND_PORT = 8000;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

// App mode: dist/ exists → load static build (no Vite needed).
// Dev mode: dist/ missing OR KIWI_FORCE_DEV=1 → connect to Vite dev server
//           with hot-module replacement.
const DIST_INDEX = path.join(__dirname, '..', 'dist', 'index.html');
const forceDev = process.env.KIWI_FORCE_DEV === '1';
const isAppMode = fs.existsSync(DIST_INDEX) && !forceDev;
const isDev = !app.isPackaged && !isAppMode;

function pollUrl(url, retries = 20, interval = 500) {
  return new Promise((resolve) => {
    let attempts = 0;
    const check = () => {
      attempts++;
      const req = http.get(url, (res) => { res.resume(); resolve(true); });
      req.on('error', () => {
        if (attempts < retries) setTimeout(check, interval);
        else resolve(false);
      });
      req.end();
    };
    check();
  });
}

async function findVitePort() {
  for (let port = 5173; port <= 5183; port++) {
    const ok = await pollUrl(`http://127.0.0.1:${port}/`, 1, 0);
    if (ok) return port;
  }
  const ok = await pollUrl(`http://127.0.0.1:5173/`, 30, 500);
  if (ok) return 5173;
  for (let port = 5174; port <= 5183; port++) {
    const ok = await pollUrl(`http://127.0.0.1:${port}/`, 5, 400);
    if (ok) return port;
  }
  return null;
}

const LOADING_HTML = `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Kiwi</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#070913;color:#c0c0d0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;overflow:hidden;user-select:none}
.c{text-align:center}
.logo{font-size:2.5rem;font-weight:800;letter-spacing:-1px;margin-bottom:24px}.ki{color:#6b7280}.wi{color:#3b82f6}
.sp{width:32px;height:32px;border:3px solid #1e1e2e;border-top:3px solid #3b82f6;border-radius:50%;animation:s .8s linear infinite;margin:0 auto 16px}
@keyframes s{to{transform:rotate(360deg)}}
.st{font-size:.85rem;opacity:.6;min-height:1.2em}
.er{color:#ef4444;font-size:.85rem;margin-top:16px;max-width:340px}
</style></head>
<body>
<div class=c>
<div class=logo><span class=ki>Ki</span><span class=wi>wi</span></div>
<div class=sp id=sp></div>
<div class=st id=s>Starting backend…</div>
<div class=er id=e></div>
</div>
<script>
const s=document.getElementById('s'),e=document.getElementById('e'),sp=document.getElementById('sp');
const msgs=['Starting backend…','Loading knowledge index…','Almost ready…'];
let i=0;const t=setInterval(()=>{s.textContent=msgs[Math.min(i++,msgs.length-1)];},2000);
window._setError=(msg)=>{clearInterval(t);sp.style.display='none';s.textContent='';e.textContent=msg;};
</script>
</body>
</html>`;

function sendStatus(win, data) {
  if (win && !win.isDestroyed()) {
    try { win.webContents.send('backend-status', data); } catch {}
  }
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 900,
    minHeight: 640,
    show: false,
    title: 'Kiwi — Offline Knowledge OS',
    icon: path.join(__dirname, '..', 'public', 'favicon.svg'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false,          // allows file:// page to load http://127.0.0.1 iframes
      allowRunningInsecureContent: true,
    },
  });

  mainWindow.removeMenu();
  mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(LOADING_HTML)}`);
  mainWindow.once('ready-to-show', () => mainWindow.show());

  if (isDev) {
    // --- Dev mode: wait for backend + Vite ---
    const [backendOk, vitePort] = await Promise.all([
      pollUrl(`${BACKEND_URL}/`, 30, 500),
      findVitePort(),
    ]);

    backendReady = backendOk;
    sendStatus(mainWindow, { running: backendOk });

    if (backendOk && vitePort) {
      mainWindow.loadURL(`http://127.0.0.1:${vitePort}`);
      if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.openDevTools();
    } else {
      const msg = !backendOk ? 'Backend failed to start — check the Kiwi-Backend terminal.' : 'Vite dev server not found — run: cd frontend && npm run dev';
      mainWindow.webContents.executeJavaScript(`window._setError && window._setError(${JSON.stringify(msg)})`).catch(() => {});
    }
  } else {
    // --- App mode: wait for backend, load from dist/ ---
    // Backend is started by start.ps1 before Electron is launched.
    // Poll generously (40 × 500ms = 20s) to allow slow startup.
    const backendOk = await pollUrl(`${BACKEND_URL}/`, 40, 500);
    backendReady = backendOk;
    sendStatus(mainWindow, { running: backendOk });

    if (backendOk) {
      mainWindow.loadFile(DIST_INDEX);
    } else {
      const msg = 'Backend did not start in time. Close and re-open the app, or check that port 8000 is free.';
      mainWindow.webContents.executeJavaScript(`window._setError && window._setError(${JSON.stringify(msg)})`).catch(() => {});
    }
  }

  mainWindow.on('closed', () => { mainWindow = null; });
}

// --- IPC Handlers ---

ipcMain.handle('select-directory', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: 'Select ZIM Archives Directory',
  });
  if (result.canceled || result.filePaths.length === 0) return null;
  return result.filePaths[0];
});

ipcMain.handle('select-files', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile', 'multiSelections'],
    title: 'Select ZIM Archive Files',
    filters: [{ name: 'ZIM Archives', extensions: ['zim', 'ZIM'] }],
  });
  if (result.canceled || result.filePaths.length === 0) return null;
  return result.filePaths;
});

ipcMain.handle('get-backend-url', () => BACKEND_URL);
ipcMain.handle('get-backend-status', () => ({ running: backendReady }));

// --- App Lifecycle ---

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
