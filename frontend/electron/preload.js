const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    isElectron: true,
    platform: process.platform,

    // Native directory picker for ZIM scanning
    selectDirectory: () => ipcRenderer.invoke('select-directory'),
    // Native multi-file picker for individual ZIM files
    selectFiles: () => ipcRenderer.invoke('select-files'),

    // Backend URL management
    getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),
    getBackendStatus: () => ipcRenderer.invoke('get-backend-status'),

    // Listen for backend status changes (runs in main process)
    onBackendStatus: (callback) => {
        const handler = (_event, status) => callback(status);
        ipcRenderer.on('backend-status', handler);
        return () => ipcRenderer.removeListener('backend-status', handler);
    },
});
