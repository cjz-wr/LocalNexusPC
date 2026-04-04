/**
 * 设置管理模块
 * OpenAI 聊天 + MCP 工具服务器管理
 */

let currentSettings = null;
let mcpConfigs = {};
let enabledMcpConfigs = [];

// 初始化设置界面
async function initSettings() {
    const settingsBtn = document.getElementById('settings-btn');
    const settingsModal = document.getElementById('settings-modal');
    const modalClose = settingsModal.querySelector('.modal-close');
    const saveSettingsBtn = document.getElementById('save-settings-btn');
    const testConnectionBtn = document.getElementById('test-connection-btn');
    const protocolSelect = document.getElementById('protocol-select');
    const addMcpConfigBtn = document.getElementById('add-mcp-config-btn');
    const mcpEditModal = document.getElementById('mcp-config-edit-modal');
    const saveMcpConfigEditBtn = document.getElementById('save-mcp-config-edit-btn');
    
    // 加载设置
    await loadSettings();
    
    // 打开设置模态框
    settingsBtn.addEventListener('click', () => {
        settingsModal.classList.add('show');

        // 后台刷新数据，避免网络请求阻塞弹窗显示
        loadSettings();
        loadMcpConfigs();
        window.Tools?.loadTools?.();
    });
    
    // 关闭模态框
    modalClose.addEventListener('click', () => {
        settingsModal.classList.remove('show');
    });
    
    // 点击模态框外部关闭
    settingsModal.addEventListener('click', (e) => {
        if (e.target === settingsModal) {
            settingsModal.classList.remove('show');
        }
    });
    
    // 协议切换
    protocolSelect.addEventListener('change', () => {
        const openaiConfig = document.getElementById('openai-config');
        const mcpConfig = document.getElementById('mcp-config');
        const toolsConfig = document.getElementById('tools-config');

        protocolSelect.value = 'openai';
        openaiConfig.style.display = 'block';
        mcpConfig.style.display = 'block';
        toolsConfig.style.display = 'block';
    });
    
    // 保存设置
    saveSettingsBtn.addEventListener('click', handleSaveSettings);
    
    // 测试连接
    testConnectionBtn.addEventListener('click', handleTestConnection);

    // MCP 工具服务器编辑相关
    addMcpConfigBtn?.addEventListener('click', () => {
        window.handleAddMcpConfig();
    });
    saveMcpConfigEditBtn?.addEventListener('click', () => {
        window.handleSaveMcpConfigEdit();
    });
    mcpEditModal?.addEventListener('click', (e) => {
        if (e.target === mcpEditModal) {
            mcpEditModal.classList.remove('show');
        }
    });
    
    // TTS 启用/禁用切换
    const ttsEnabledCheckbox = document.getElementById('tts-enabled');
    const ttsOptions = document.getElementById('tts-options');
    
    ttsEnabledCheckbox.addEventListener('change', () => {
        ttsOptions.style.display = ttsEnabledCheckbox.checked ? 'block' : 'none';
    });
    
    // 调试：监听 TTS 输入框的焦点事件
    ['tts-rate', 'tts-pitch', 'tts-volume'].forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            input.addEventListener('focus', () => {
                console.log(`[DEBUG] ${id} focused, value:`, input.value);
            });
            input.addEventListener('input', () => {
                console.log(`[DEBUG] ${id} changed to:`, input.value);
            });
            input.addEventListener('click', () => {
                console.log(`[DEBUG] ${id} clicked`);
            });
        }
    });
}

// 加载设置
async function loadSettings() {
    try {
        currentSettings = await API.getSettings();
        console.log('Loaded settings:', currentSettings);
        
        // 当前版本固定使用 OpenAI 作为聊天协议
        currentSettings.protocol = 'openai';
        document.getElementById('protocol-select').value = 'openai';
        
        // OpenAI 配置
        document.getElementById('openai-api-key').value = currentSettings.openai?.api_key || '';
        document.getElementById('openai-base-url').value = currentSettings.openai?.base_url || 'https://api.openai.com/v1';
        document.getElementById('openai-model').value = currentSettings.openai?.model || 'gpt-3.5-turbo';
        document.getElementById('openai-max-tokens').value = currentSettings.openai?.max_tokens || 2048;
        document.getElementById('openai-temperature').value = currentSettings.openai?.temperature || 0.7;
        
        // MCP 单配置（向后兼容）
        document.getElementById('mcp-server-url').value = currentSettings.mcp?.server_url || 'http://localhost:8080';
        document.getElementById('mcp-model').value = currentSettings.mcp?.model || 'default';
        document.getElementById('mcp-auth-token').value = currentSettings.mcp?.auth_token || '';
        
        // TTS 配置
        const ttsEnabled = currentSettings.tts?.enabled || false;
        document.getElementById('tts-enabled').checked = ttsEnabled;
        document.getElementById('tts-voice').value = currentSettings.tts?.voice || 'zh-CN-XiaoxiaoNeural';
        document.getElementById('tts-rate').value = currentSettings.tts?.rate || '+0%';
        document.getElementById('tts-pitch').value = currentSettings.tts?.pitch || '+0Hz';
        document.getElementById('tts-volume').value = currentSettings.tts?.volume || '+0%';
        
        // 记忆功能配置
        document.getElementById('memory-enabled').checked = currentSettings.memory_enabled ?? true;
        
        // 记忆精炼配置
        const memorySettings = currentSettings.memory || {};
        document.getElementById('refine-model').value = memorySettings.refine_model || '';
        document.getElementById('refine-api-key').value = memorySettings.refine_model_api_key || '';
        document.getElementById('refine-base-url').value = memorySettings.refine_model_base_url || '';
        document.getElementById('trigger-percent').value = (memorySettings.trigger_token_percent || 0.5) * 100;
        document.getElementById('sliding-percent').value = (memorySettings.sliding_window_percent || 0.85) * 100;
        
        // 根据启用状态显示/隐藏 TTS 选项
        document.getElementById('tts-options').style.display = ttsEnabled ? 'block' : 'none';

        // 触发协议切换事件以显示正确的配置面板
        document.getElementById('protocol-select').dispatchEvent(new Event('change'));
        
        // 更新模型选择器
        updateModelSelector(currentSettings);
        
    } catch (error) {
        console.error('Failed to load settings:', error);
        showToast(`加载设置失败：${error.message}`, 'error');
    }
}

// 加载 MCP 多配置
async function loadMcpConfigs() {
    try {
        const response = await API.getMcpConfigs();
        mcpConfigs = response.configs || {};
        enabledMcpConfigs = response.enabled_mcp_configs || [];
        
        console.log('Loaded MCP configs:', mcpConfigs);
        console.log('Enabled MCP configs:', enabledMcpConfigs);
        
        renderMcpConfigList();
        await window.Tools?.loadTools?.();
    } catch (error) {
        console.error('Failed to load MCP configs:', error);
        showToast(`加载 MCP 配置失败：${error.message}`, 'error');
    }
    
    // 将 MCP 配置暴露到全局，便于其他模块使用
    window.mcpConfigs = mcpConfigs;
}

// 渲染 MCP 配置列表
function renderMcpConfigList() {
    const configList = document.getElementById('mcp-config-list');
    if (!configList) return;
    
    configList.innerHTML = '';
    
    const configIds = Object.keys(mcpConfigs);
    
    if (configIds.length === 0) {
        configList.innerHTML = '<div class="empty-state">暂无 MCP 配置，请点击"添加配置"按钮创建新配置</div>';
        return;
    }
    
    configIds.forEach(configId => {
        const config = mcpConfigs[configId]; // 获取配置项
        const isEnabled = enabledMcpConfigs.includes(configId); // 检查该配置项是否已启用
        
        const configItem = document.createElement('div');
        configItem.className = `mcp-config-item ${isEnabled ? 'enabled' : ''}`;
        configItem.dataset.configId = configId;
        
        configItem.innerHTML = `
            <div class="config-item-header">
                <div class="config-item-info">
                    <input type="checkbox" class="config-enable-checkbox" 
                           data-config-id="${configId}" 
                           ${isEnabled ? 'checked' : ''}
                           title="启用/禁用此配置">
                    <span class="config-name">${escapeHtml(config.name || configId)}</span>
                    <span class="config-status">${isEnabled ? '✓ 已启用' : '✗ 已禁用'}</span>
                </div>
                <div class="config-item-actions">
                    <button type="button" class="btn btn-sm btn-edit" data-action="edit" data-config-id="${configId}" title="编辑">
                        <svg width="16" height="16" viewBox="0 0 24 24">
                            <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" fill="currentColor"/>
                        </svg>
                    </button>
                    <button type="button" class="btn btn-sm btn-delete" data-action="delete" data-config-id="${configId}" title="删除">
                        <svg width="16" height="16" viewBox="0 0 24 24">
                            <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/>
                        </svg>
                    </button>
                </div>
            </div>
            <div class="config-item-details">
                <div class="config-detail-row">
                    <span class="detail-label">服务器地址:</span>
                    <span class="detail-value">${escapeHtml(config.server_url || '')}</span>
                </div>
                <div class="config-detail-row">
                    <span class="detail-label">模型:</span>
                    <span class="detail-value">${escapeHtml(config.model || '')}</span>
                </div>
            </div>
        `;
        
        configList.appendChild(configItem);
    });
    
    // 绑定编辑/删除事件
    configList.querySelectorAll('[data-action="edit"]').forEach(button => {
        button.addEventListener('click', () => {
            editMcpConfig(button.dataset.configId);
        });
    });

    configList.querySelectorAll('[data-action="delete"]').forEach(button => {
        button.addEventListener('click', () => {
            deleteMcpConfig(button.dataset.configId);
        });
    });

    // 绑定启用/禁用事件
    configList.querySelectorAll('.config-enable-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', async (e) => {
            const configId = e.target.dataset.configId;
            const enabled = e.target.checked;
            
            try {
                await API.toggleMcpConfigEnabled(configId, enabled);
                await loadMcpConfigs();
                
                if (enabled) {
                    showToast('已启用工具服务器', 'success');
                } else {
                    const remainingEnabled = enabledMcpConfigs.filter(id => id !== configId).length;
                    if (remainingEnabled === 0) {
                        showToast('已禁用所有工具服务器', 'info');
                    } else {
                        showToast('已禁用工具服务器', 'success');
                    }
                }
            } catch (error) {
                console.error('Failed to toggle MCP config:', error);
                showToast(`操作失败：${error.message}`, 'error');
                e.target.checked = !enabled; // 恢复状态
            }
        });
    });
}

// 编辑 MCP 配置
window.editMcpConfig = async function(configId) {
    const config = mcpConfigs[configId];
    if (!config) return;
    
    // 显示编辑表单
    const editModal = document.getElementById('mcp-config-edit-modal');
    const editForm = document.getElementById('mcp-config-edit-form'); // 添加
    
    document.getElementById('edit-config-id').value = configId;
    document.getElementById('edit-config-name').value = config.name || '';
    document.getElementById('edit-config-server-url').value = config.server_url || '';
    document.getElementById('edit-config-model').value = config.model || '';
    document.getElementById('edit-config-auth-token').value = config.auth_token || '';
    
    editModal.classList.add('show');
};

// 保存 MCP 配置编辑
window.handleSaveMcpConfigEdit = async function handleSaveMcpConfigEdit() {
    const configId = document.getElementById('edit-config-id').value;
    const config = {
        name: document.getElementById('edit-config-name').value.trim(),
        server_url: document.getElementById('edit-config-server-url').value.trim(),
        model: document.getElementById('edit-config-model').value.trim(),
        auth_token: document.getElementById('edit-config-auth-token').value.trim()
    };
    
    // 验证必填字段
    if (!config.name) {
        showToast('请输入配置名称', 'error');
        return;
    }
    
    if (!config.server_url) {
        showToast('请输入服务器地址', 'error');
        return;
    }
    
    try {
        await API.updateMcpConfig(configId, config);
        await loadMcpConfigs();
        document.getElementById('mcp-config-edit-modal').classList.remove('show');
        showToast('配置已保存', 'success');
    } catch (error) {
        console.error('Failed to update MCP config:', error);
        showToast(`保存失败：${error.message}`, 'error');
    }
}

// 删除 MCP 配置
window.deleteMcpConfig = async function(configId) {
    if (!confirm('确定要删除此 MCP 配置吗？此操作不可恢复。')) {
        return;
    }
    
    try {
        await API.deleteMcpConfig(configId);
        await loadMcpConfigs();
        showToast('配置已删除', 'success');
    } catch (error) {
        console.error('Failed to delete MCP config:', error);
        showToast(`删除失败：${error.message}`, 'error');
    }
};

// 添加新的 MCP 配置
window.handleAddMcpConfig = async function handleAddMcpConfig() {
    const config = {
        name: `MCP 配置 ${Object.keys(mcpConfigs).length + 1}`,
        server_url: 'http://localhost:8080',
        model: 'default',
        auth_token: ''
    };
    
    try {
        const result = await API.createMcpConfig(config);
        await loadMcpConfigs();
        
        // 自动编辑新添加的配置
        setTimeout(() => {
            editMcpConfig(result.config_id);
        }, 300);
        
        showToast('配置已添加', 'success');
    } catch (error) {
        console.error('Failed to create MCP config:', error);
        showToast(`添加失败：${error.message}`, 'error');
    }
}

// HTML 转义辅助函数
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 保存设置
async function handleSaveSettings() {
    const protocol = 'openai';
    
    const settings = {
        protocol,
        openai: {
            api_key: document.getElementById('openai-api-key').value.trim(),
            base_url: document.getElementById('openai-base-url').value.trim(),
            model: document.getElementById('openai-model').value.trim(),
            max_tokens: parseInt(document.getElementById('openai-max-tokens').value),
            temperature: parseFloat(document.getElementById('openai-temperature').value)
        },
        mcp: {
            server_url: document.getElementById('mcp-server-url').value.trim(),
            model: document.getElementById('mcp-model').value.trim(),
            auth_token: document.getElementById('mcp-auth-token').value.trim()
        },
        mcp_configs: mcpConfigs,
        enabled_mcp_configs: enabledMcpConfigs,
        tts: {
            enabled: document.getElementById('tts-enabled').checked,
            voice: document.getElementById('tts-voice').value,
            rate: document.getElementById('tts-rate').value,
            pitch: document.getElementById('tts-pitch').value,
            volume: document.getElementById('tts-volume').value
        },
        memory_enabled: document.getElementById('memory-enabled').checked,
        memory: {
            refine_model: document.getElementById('refine-model').value.trim(),
            refine_model_api_key: document.getElementById('refine-api-key').value.trim(),
            refine_model_base_url: document.getElementById('refine-base-url').value.trim(),
            trigger_token_percent: parseFloat(document.getElementById('trigger-percent').value) / 100,
            sliding_window_percent: parseFloat(document.getElementById('sliding-percent').value) / 100
        }
    };
    
    // 验证必填字段
    if (protocol === 'openai' && !settings.openai.api_key) {
        showToast('请输入 API Key', 'error');
        return;
    }
    
    
    try {
        await API.saveSettings(settings);
        currentSettings = settings;
        await window.Tools?.loadTools?.();
        showToast('设置已保存', 'success');
        
        // 更新模型选择器
        updateModelSelector(settings);
        
        // 关闭模态框
        document.getElementById('settings-modal').classList.remove('show');
        
    } catch (error) {
        console.error('Failed to save settings:', error);
        showToast(`保存设置失败：${error.message}`, 'error');
    }
}

// 测试连接
async function handleTestConnection() {
    const protocol = 'openai';
    
    const config = {
        openai: {
            api_key: document.getElementById('openai-api-key').value.trim(),
            base_url: document.getElementById('openai-base-url').value.trim(),
            model: document.getElementById('openai-model').value.trim(),
            max_tokens: parseInt(document.getElementById('openai-max-tokens').value),
            temperature: parseFloat(document.getElementById('openai-temperature').value)
        },
        mcp: {
            server_url: document.getElementById('mcp-server-url').value.trim(),
            model: document.getElementById('mcp-model').value.trim(),
            auth_token: document.getElementById('mcp-auth-token').value.trim()
        }
    };
    
    try {
        showToast('正在测试连接...', 'info');
        const result = await API.testConnection(protocol, config);
        
        if (result.success) {
            showToast('连接测试成功！', 'success');
        } else {
            showToast(`连接测试失败：${result.error}`, 'error');
        }
    } catch (error) {
        console.error('Connection test failed:', error);
        showToast(`连接测试失败：${error.message}`, 'error');
    }
}

// 更新模型选择器
function updateModelSelector(settings) {
    const modelSelect = document.getElementById('model-select');
    let models = [];

    if (settings.openai?.model) {
        models = [settings.openai.model];
    }

    if (models.length === 0) {
        models = ['default'];
    }
    
    // 更新下拉框
    modelSelect.innerHTML = '';
    models.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = model;
        modelSelect.appendChild(option);
    });
}

// 获取当前设置
function getCurrentSettings() {
    return currentSettings;
}