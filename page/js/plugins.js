/**
 * 插件管理模块
 */

let pluginsList = [];

// 初始化插件管理界面
async function initPlugins() {
    const pluginsBtn = document.getElementById('plugins-btn');
    const pluginsModal = document.getElementById('plugins-modal');
    const modalClose = pluginsModal.querySelector('.modal-close');
    const closePluginsBtn = document.getElementById('close-plugins-btn');
    
    // 加载插件列表
    await loadPlugins();
    
    // 打开插件模态框
    pluginsBtn.addEventListener('click', async () => {
        await loadPlugins();
        renderPluginsList();
        pluginsModal.classList.add('show');
    });
    
    // 关闭模态框
    modalClose.addEventListener('click', () => {
        pluginsModal.classList.remove('show');
    });
    
    closePluginsBtn.addEventListener('click', () => {
        pluginsModal.classList.remove('show');
    });
    
    // 点击模态框外部关闭
    pluginsModal.addEventListener('click', (e) => {
        if (e.target === pluginsModal) {
            pluginsModal.classList.remove('show');
        }
    });
}

// 加载插件列表
async function loadPlugins() {
    try {
        pluginsList = await API.getPlugins();
        console.log('Loaded plugins:', pluginsList);
    } catch (error) {
        console.error('Failed to load plugins:', error);
        showToast(`加载插件列表失败：${error.message}`, 'error');
        pluginsList = [];
    }
}

// 渲染插件列表
function renderPluginsList() {
    const pluginsListEl = document.getElementById('plugins-list');
    
    if (pluginsList.length === 0) {
        pluginsListEl.innerHTML = '<p style="text-align: center; color: #999; padding: 20px;">暂无可用插件</p>';
        return;
    }
    
    pluginsListEl.innerHTML = '';
    
    pluginsList.forEach(plugin => {
        const pluginItem = document.createElement('div');
        pluginItem.className = 'plugin-item';
        
        pluginItem.innerHTML = `
            <div class="plugin-info">
                <h4>${plugin.name} <small style="color: #999;">v${plugin.version}</small></h4>
                <p>${plugin.description || '无描述'}</p>
            </div>
            <label class="plugin-toggle">
                <input type="checkbox" ${plugin.enabled ? 'checked' : ''} 
                       data-plugin-name="${plugin.name}"
                       onchange="togglePlugin(this)">
                <span class="toggle-slider"></span>
            </label>
        `;
        
        pluginsListEl.appendChild(pluginItem);
    });
}

// 切换插件状态
window.togglePlugin = async function(checkbox) {
    const pluginName = checkbox.dataset.pluginName;
    const enabled = checkbox.checked;
    
    try {
        await API.updatePluginStatus(pluginName, enabled);
        showToast(`${pluginName} 已${enabled ? '启用' : '禁用'}`, 'success');
        
        // 更新本地列表
        const plugin = pluginsList.find(p => p.name === pluginName);
        if (plugin) {
            plugin.enabled = enabled;
        }
    } catch (error) {
        console.error('Failed to update plugin status:', error);
        showToast(`更新插件状态失败：${error.message}`, 'error');
        checkbox.checked = !enabled; // 恢复状态
    }
};

// 获取启用的插件列表
function getEnabledPlugins() {
    return pluginsList.filter(p => p.enabled);
}
