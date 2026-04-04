const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

// ==================== 配置管理 ====================
// 端口配置优先级：环境变量 > 配置文件 > 默认值
function getBackendPort() {
  // 1. 优先使用环境变量
  if (process.env.BACKEND_PORT) {
    console.log(`Using backend port from environment: ${process.env.BACKEND_PORT}`);
    return process.env.BACKEND_PORT;
  }
  
  // 2. 尝试从配置文件读取
  try {
    const portConfigPath = path.join(__dirname, '../backend/backend_port.json');
    if (fs.existsSync(portConfigPath)) {
      const portConfig = JSON.parse(fs.readFileSync(portConfigPath, 'utf-8'));
      if (portConfig.port) {
        console.log(`Using backend port from config file: ${portConfig.port}`);
        return portConfig.port;
      }
    }
  } catch (error) {
    console.warn('Failed to load backend_port.json:', error.message);
  }
  
  // 3. 使用默认端口
  console.log(`Using default backend port: 8765`);
  return '8765';
}

const DEFAULT_BACKEND_PORT = getBackendPort();
let mainWindow;
let pythonProcess = null;
let backendPort = DEFAULT_BACKEND_PORT;

// 启动 Python 后端
function startPythonBackend() {
  return new Promise((resolve, reject) => {
    const isDev = process.argv.includes('--dev');
    let pythonPath;
    let scriptPath;

    if (isDev) {
      // 开发模式：直接使用 Python 解释器
      pythonPath = 'python';
      scriptPath = path.join(__dirname, '../backend/main.py');
    } else {
      // 生产模式：使用打包后的可执行文件
      pythonPath = path.join(process.resourcesPath, 'backend', 'dist', 'backend_main.exe');
      scriptPath = '';
    }

    const args = scriptPath ? [scriptPath] : [];

    console.log(`Starting Python backend on port ${backendPort}...`);
    
    pythonProcess = spawn(pythonPath, args, {
      cwd: path.join(__dirname, '../backend'),
      env: { ...process.env, BACKEND_PORT: backendPort }, // 传递端口环境变量
      stdio: ['pipe', 'pipe', 'pipe']
    });

    // 监听 stdout 获取日志和确认启动
    pythonProcess.stdout.on('data', (data) => {
      const output = data.toString();
      console.log(`Python stdout: ${output}`);
      
      // 检测后端是否已启动（通过特定标志）
      if (output.includes('Backend server started') || output.includes('Uvicorn running')) {
        console.log(`Backend server confirmed started on port ${backendPort}`);
        resolve(backendPort);
      }
    });

    // 监听 stderr 获取错误信息
    pythonProcess.stderr.on('data', (data) => {
      const error = data.toString();
      console.error(`Python stderr: ${error}`);
      
      // 如果是手动启动模式，后端可能会输出启动确认到 stderr
      if (error.includes('Backend server started') || error.includes('Uvicorn running')) {
        console.log(`Backend server confirmed started on port ${backendPort}`);
        resolve(backendPort);
      }
    });

    pythonProcess.on('close', (code) => {
      console.log(`Python process exited with code ${code}`);
      if (code !== 0 && !mainWindow?.isDestroyed()) {
        mainWindow.webContents.send('backend-error', `后端进程已退出，代码：${code}`);
      }
    });

    pythonProcess.on('error', (err) => {
      console.error('Failed to start Python process:', err);
      pythonProcess = null; // 清空进程引用
      reject(new Error(`无法启动 Python 后端：${err.message}`));
    });

    // 监听进程退出
    pythonProcess.on('exit', (code, signal) => {
      console.log(`Python process exited with code ${code}, signal ${signal}`);
      pythonProcess = null; // 清空进程引用
    });

    // 超时处理
    setTimeout(() => {
      // 如果已经超过合理时间，但进程还在运行，认为启动成功
      if (pythonProcess && !pythonProcess.killed) {
        console.log(`Backend startup timeout exceeded, assuming running on port ${backendPort}`);
        resolve(backendPort);
      } else if (!backendPort) {
        reject(new Error('启动后端超时，未检测到服务启动'));
      }
    }, 15000); // 增加到 15 秒超时
  });
}

// 创建主窗口
function createWindow(port) {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    autoHideMenuBar: true,
    
    webPreferences: {
      devTools: true,
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    },
    icon: path.join(__dirname, '../page/img/icon.png'),
    title: 'LocalNexus PC - AI Chat'
  });

  mainWindow.loadFile(path.join(__dirname, '../page/html/index.html'));

  // 将端口传递给渲染进程
  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow.webContents.send('backend-port', port);
    console.log(`Backend port ${port} sent to renderer`);
  });

  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// 应用就绪时创建窗口
app.whenReady().then(async () => {
  try {
    const port = await startPythonBackend();
    createWindow(port);
  } catch (error) {
    console.error('Failed to start backend:', error);
    // 即使后端启动失败，也创建窗口显示错误信息
    createWindow(backendPort); // 仍然传递配置的端口
  }
});

// IPC 处理程序
ipcMain.handle('get-backend-port', () => {
  return backendPort;
});

ipcMain.handle('send-http-request', async (event, config) => {
  const http = require('http');
  const https = require('https');
  const { URL } = require('url');

  return new Promise((resolve, reject) => {
    const url = new URL(config.url);
    const lib = url.protocol === 'https:' ? https : http;

    // 使用 URL 中的端口，如果没有指定则使用 backendPort
    let port = url.port;
    if (!port) {
      // 如果 URL 没有明确指定端口，根据协议使用默认端口
      if (url.protocol === 'https:') {
        port = 443;
      } else {
        port = backendPort || 8765;
      }
    }

    const options = {
      hostname: url.hostname,
      port: port,
      path: url.pathname + url.search,
      method: config.method || 'GET',
      headers: config.headers || {}
    };
    const requestTimeout = Number(config.timeout) || 10000;

    console.log(`[HTTP Request] ${config.method} ${url.protocol}//${url.hostname}:${port}${url.pathname}${url.search}`);

    const req = lib.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => {
        data += chunk;
      });
      res.on('end', () => {
        try {
          resolve({
            status: res.statusCode,
            data: JSON.parse(data)
          });
        } catch (e) {
          resolve({
            status: res.statusCode,
            data: data
          });
        }
      });
    });

    req.setTimeout(requestTimeout, () => {
      req.destroy(new Error(`请求超时 (${requestTimeout}ms)`));
    });

    req.on('error', (error) => {
      console.error('[HTTP Request Error]', error.message);
      reject(new Error(`无法连接到后端服务 (${url.hostname}:${port}) - ${error.message}`));
    });

    if (config.body) {
      req.write(JSON.stringify(config.body));
    }

    req.end();
  });
});

// 应用退出时终止 Python 进程
app.on('will-quit', () => {
  if (pythonProcess) {
    console.log('Terminating Python backend...');
    try {
      if (process.platform === 'win32') {
        if (pythonProcess.pid) {
          spawn('taskkill', ['/pid', pythonProcess.pid.toString(), '/f', '/t']);
        }
      } else {
        pythonProcess.kill('SIGTERM');
      }
    } catch (error) {
      console.error('Error terminating Python process:', error.message);
    }
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    app.whenReady().then(async () => {
      // 如果 Python 进程不存在或已退出，重新启动
      if (!pythonProcess || pythonProcess.killed) {
        try {
          await startPythonBackend();
        } catch (error) {
          console.error('Failed to restart backend:', error);
        }
      }
      // 重新创建窗口（如果已存在则不创建）
      if (!mainWindow) {
        createWindow(backendPort);
      }
    });
  }
});
