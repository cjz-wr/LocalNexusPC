/**
 * API 通信模块
 * 负责与 Python 后端进行 HTTP 和 WebSocket 通信
 */

let backendPort = null;
let wsConnection = null;

// 提前导出空的 API 对象，防止其他脚本引用时报错
window.API = {
    init: null,
    getConversations: null,
    createConversation: null,
    deleteConversation: null,
    updateConversationTitle: null,
    getConversationMessages: null,
    clearConversationMessages: null,
    getSettings: null,
    saveSettings: null,
    testConnection: null,
    getMcpConfigs: null,
    createMcpConfig: null,
    updateMcpConfig: null,
    deleteMcpConfig: null,
    toggleMcpConfigEnabled: null,
    getPlugins: null,
    updatePluginStatus: null,
    getTools: null,
    updateToolStatus: null,
    getSystemPrompts: null,
    createSystemPrompt: null,
    updateSystemPrompt: null,
    deleteSystemPrompt: null,
    getActiveSystemPrompt: null,
    setActiveSystemPrompt: null,
    streamChat: null,
    closeWebSocket: null
};

// 初始化，获取后端端口
async function initAPI() {
    try {
        // 从 Electron 主进程获取后端端口
        backendPort = await window.electronAPI.getBackendPort();
        console.log('Backend port:', backendPort);
        
        // 监听后端错误
        window.electronAPI.onBackendError((error) => {
            showToast(`后端错误：${error}`, 'error');
        });
        
        return true;
    } catch (error) {
        console.error('Failed to get backend port:', error);
        showToast('无法连接到后端服务', 'error');
        return false;
    }
}

// 构建后端 API URL
function buildURL(path) {
    if (!backendPort) {
        throw new Error('后端端口未设置');
    }
    return `http://localhost:${backendPort}${path}`;
}

// 发送 HTTP 请求
async function sendRequest(method, path, body = null) {
    try {
        const config = {
            method: method,
            url: buildURL(path),
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        if (body && method !== 'GET') {
            config.body = body;
        }
        
        const response = await window.electronAPI.sendHttpRequest(config);
        
        if (response.status >= 200 && response.status < 300) {
            return response.data;
        } else {
            const errorMessage = response.data?.detail || response.data?.message || `HTTP ${response.status}`;
            throw new Error(errorMessage);
        }
    } catch (error) {
        console.error('HTTP request failed:', error);
        throw error;
    }
}

// ===== 对话管理 API =====

// 获取所有对话列表
async function getConversations() {
    return await sendRequest('GET', '/conversations');
}

// 新建对话
async function createConversation(title = null) {
    const body = title ? { title } : {};
    return await sendRequest('POST', '/conversations', body);
}

// 删除对话
async function deleteConversation(conversationId) {
    return await sendRequest('DELETE', `/conversations/${conversationId}`);
}

// 更新对话标题
async function updateConversationTitle(conversationId, title) {
    return await sendRequest('PUT', `/conversations/${conversationId}/title`, { title });
}

// 获取对话消息列表
async function getConversationMessages(conversationId) {
    return await sendRequest('GET', `/conversations/${conversationId}/messages`);
}

// 清空对话消息
async function clearConversationMessages(conversationId) {
    return await sendRequest('POST', `/conversations/${conversationId}/clear`);
}

// ===== 设置管理 API =====

// 获取设置
async function getSettings() {
    return await sendRequest('GET', '/settings');
}

// 保存设置
async function saveSettings(settings) {
    return await sendRequest('POST', '/settings', settings);
}

// 测试连接
async function testConnection(protocol, config) {
    return await sendRequest('POST', '/test-connection', { protocol, ...(config || {}) });
}

// ===== MCP 配置管理 API =====

// 获取所有 MCP 配置
async function getMcpConfigs() {
    return await sendRequest('GET', '/mcp-configs');
}

// 创建新的 MCP 配置
async function createMcpConfig(config) {
    return await sendRequest('POST', '/mcp-configs', config);
}

// 更新指定的 MCP 配置
async function updateMcpConfig(configId, config) {
    return await sendRequest('PUT', `/mcp-configs/${configId}`, config);
}

// 删除指定的 MCP 配置
async function deleteMcpConfig(configId) {
    return await sendRequest('DELETE', `/mcp-configs/${configId}`);
}

// 切换 MCP 配置的启用状态
async function toggleMcpConfigEnabled(configId, enabled) {
    return await sendRequest('POST', `/mcp-configs/toggle-enabled?config_id=${configId}&enabled=${enabled}`);
}

// ===== 插件管理 API =====

// 获取所有可用插件及其启用状态
async function getPlugins() {
    return await sendRequest('GET', '/plugins');
}

// 启用/禁用插件
async function updatePluginStatus(pluginName, enabled) {
    return await sendRequest('PUT', `/plugins/${pluginName}/status`, { enabled });
}

// ===== 工具管理 API =====

// 获取所有可用工具及其启用状态
async function getTools() {
    return await sendRequest('GET', '/tools');
}

// 启用/禁用工具
async function updateToolStatus(toolName, enabled) {
    return await sendRequest('PUT', `/tools/${toolName}/status`, { enabled });
}

// ===== 系统提示词管理 API =====

// 获取所有系统提示词
async function getSystemPrompts() {
    return await sendRequest('GET', '/system-prompts');
}

// 创建系统提示词
async function createSystemPrompt(promptData) {
    return await sendRequest('POST', '/system-prompts', promptData);
}

// 更新系统提示词
async function updateSystemPrompt(promptId, promptData) {
    return await sendRequest('PUT', `/system-prompts/${promptId}`, promptData);
}

// 删除系统提示词
async function deleteSystemPrompt(promptId) {
    return await sendRequest('DELETE', `/system-prompts/${promptId}`);
}

// 获取当前激活的系统提示词
async function getActiveSystemPrompt() {
    return await sendRequest('GET', '/system-prompts/active');
}

// 设置激活的系统提示词
async function setActiveSystemPrompt(promptId) {
    return await sendRequest('POST', '/system-prompts/active', { id: promptId });
}

// ===== WebSocket 流式聊天 =====

// 建立 WebSocket 连接
function connectWebSocket() {
    return new Promise((resolve, reject) => {
        if (!backendPort) {
            reject(new Error('后端端口未设置'));
            return;
        }
        
        const wsUrl = `ws://localhost:${backendPort}/ws/chat`;
        console.log('Connecting to WebSocket:', wsUrl);
        
        wsConnection = new WebSocket(wsUrl);
        
        wsConnection.onopen = () => {
            console.log('WebSocket connected');
            resolve(wsConnection);
        };
        
        wsConnection.onerror = (error) => {
            console.error('WebSocket error:', error);
            reject(error);
        };
        
        wsConnection.onclose = () => {
            console.log('WebSocket closed');
            wsConnection = null;
        };
    });
}

// 发送聊天消息（流式）
async function streamChat(conversationId, message, callbacks) {
    const { onToken, onStart, onComplete, onError, onToolCallStart, onToolCallResult, onTTSStart, onTTSAudio, onTTSEnd, onTTSError } = callbacks;
    
    if (!wsConnection || wsConnection.readyState !== WebSocket.OPEN) {
        try {
            await connectWebSocket();
        } catch (error) {
            onError?.(new Error('WebSocket 连接失败'));
            return;
        }
    }
    
    return new Promise((resolve, reject) => {
        const requestId = generateUUID();
        let isComplete = false;
        
        // 定义消息处理器
        const messageHandler = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('WebSocket received:', data);
                
                switch (data.type) {
                    case 'start':
                        onStart?.(data);
                        break;
                        
                    case 'token':
                        if (!isComplete) {
                            onToken?.(data.content);
                        }
                        break;
                        
                    case 'end':
                        isComplete = true;
                        wsConnection.removeEventListener('message', messageHandler);
                        onComplete?.(data);
                        resolve(data);
                        break;

                    case 'tool_call_start':
                        onToolCallStart?.(data);
                        break;

                    case 'tool_call_result':
                        onToolCallResult?.(data);
                        break;
                    
                    // TTS 相关消息
                    case 'tts_start':
                        onTTSStart?.(data);
                        break;
                    
                    case 'tts_audio':
                        onTTSAudio?.(data.data);
                        break;
                    
                    case 'tts_end':
                        onTTSEnd?.(data);
                        break;
                    
                    case 'tts_error':
                        onTTSError?.(new Error(data.error));
                        break;
                        
                    case 'error':
                        isComplete = true;
                        wsConnection.removeEventListener('message', messageHandler);
                        onError?.(new Error(data.content));
                        reject(new Error(data.content));
                        break;
                        
                    default:
                        console.warn('Unknown message type:', data.type);
                }
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
                onError?.(error);
                reject(error);
            }
        };
        
        // 添加消息监听器
        wsConnection.addEventListener('message', messageHandler);
        
        // 发送聊天请求
        const request = {
            id: requestId,
            conversation_id: conversationId,
            message: message
        };
        
        console.log('Sending chat request:', request);
        wsConnection.send(JSON.stringify(request));
        
        // 超时处理
        setTimeout(() => {
            if (!isComplete) {
                wsConnection.removeEventListener('message', messageHandler);
                const timeoutError = new Error('请求超时');
                onError?.(timeoutError);
                reject(timeoutError);
            }
        }, 6000000); // 60 秒超时
    });
}

// 关闭 WebSocket 连接
function closeWebSocket() {
    if (wsConnection) {
        wsConnection.close();
        wsConnection = null;
    }
}

// 导出 API 函数（覆盖之前的空对象）
window.API = {
    init: initAPI,
    
    // 对话管理
    getConversations,
    createConversation,
    deleteConversation,
    updateConversationTitle,
    getConversationMessages,
    clearConversationMessages,
    
    // 设置管理
    getSettings,
    saveSettings,
    testConnection,
    
    // MCP 配置管理
    getMcpConfigs,
    createMcpConfig,
    updateMcpConfig,
    deleteMcpConfig,
    toggleMcpConfigEnabled,
    
    // 插件管理
    getPlugins,
    updatePluginStatus,
    
    // 工具管理
    getTools,
    updateToolStatus,
    
    // 系统提示词管理
    getSystemPrompts,
    createSystemPrompt,
    updateSystemPrompt,
    deleteSystemPrompt,
    getActiveSystemPrompt,
    setActiveSystemPrompt,
    
    // WebSocket 聊天
    streamChat,
    closeWebSocket
};
