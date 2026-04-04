const { contextBridge, ipcRenderer } = require('electron');

// 向渲染进程暴露 API
contextBridge.exposeInMainWorld('electronAPI', {
  // 获取后端端口
  getBackendPort: () => ipcRenderer.invoke('get-backend-port'),

  // 发送 HTTP 请求
  sendHttpRequest: (config) => ipcRenderer.invoke('send-http-request', config),

  // 监听后端端口消息
  onBackendPort: (callback) => {
    ipcRenderer.on('backend-port', (event, port) => callback(port));
  },

  // 监听后端错误
  onBackendError: (callback) => {
    ipcRenderer.on('backend-error', (event, error) => callback(error));
  },

  // 移除监听器
  removeBackendPortListener: (callback) => {
    ipcRenderer.removeListener('backend-port', callback);
  },

  removeBackendErrorListener: (callback) => {
    ipcRenderer.removeListener('backend-error', callback);
  }
});
