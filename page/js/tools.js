/**
 * 工具管理模块
 * 负责聚合展示本地插件工具与 MCP 远程工具
 */

let toolsContainer = null;
let toolsList = [];
let toolsSearchInput = null;
let currentFilter = '';

async function initTools() {
    toolsContainer = document.getElementById('tools-list');
    if (!toolsContainer) {
        console.warn('Tools container not found');
        return;
    }

    // 创建搜索框（如果不存在）
    const toolsConfig = document.getElementById('tools-config');
    if (toolsConfig && !document.getElementById('tools-search')) {
        const searchInput = document.createElement('input');
        searchInput.id = 'tools-search';
        searchInput.className = 'tools-search';
        searchInput.placeholder = '搜索工具名称或描述...';
        searchInput.addEventListener('input', (e) => {
            currentFilter = e.target.value.toLowerCase();
            renderToolsList();
        });
        // 插入到工具列表之前
        const header = toolsConfig.querySelector('h3');
        if (header && header.nextSibling) {
            toolsConfig.insertBefore(searchInput, header.nextSibling);
        } else {
            toolsConfig.appendChild(searchInput);
        }
        toolsSearchInput = searchInput;
    }

    await loadTools();
}

async function loadTools() {
    try {
        toolsList = await window.API.getTools();
        renderToolsList();
    } catch (error) {
        console.error('Failed to load tools:', error);
        showToast('加载工具列表失败', 'error');
    }
}

function renderToolsList() {
    if (!toolsContainer) return;
    toolsContainer.innerHTML = '';

    // 过滤工具
    let filteredTools = toolsList;
    if (currentFilter) {
        filteredTools = toolsList.filter(tool => 
            tool.display_name?.toLowerCase().includes(currentFilter) ||
            tool.name?.toLowerCase().includes(currentFilter) ||
            tool.description?.toLowerCase().includes(currentFilter) ||
            tool.provider_name?.toLowerCase().includes(currentFilter)
        );
    }

    if (!filteredTools.length) {
        toolsContainer.innerHTML = '<div class="no-tools">暂无可用工具，请先启用本地插件工具或可访问的 MCP 工具服务器</div>';
        return;
    }

    // 按 source_id 分组
    const grouped = {};
    filteredTools.forEach(tool => {
        const groupKey = tool.source_id || 'unknown';
        if (!grouped[groupKey]) grouped[groupKey] = [];
        grouped[groupKey].push(tool);
    });

    // 渲染分组
    for (const [groupId, groupTools] of Object.entries(grouped)) {
        const groupHeader = document.createElement('div');
        groupHeader.className = 'tools-group-header';
        // 获取显示名称：如果是 MCP 配置，使用配置名称；否则使用 groupId
        const mcpConfig = window.mcpConfigs?.[groupId];
        const groupDisplayName = mcpConfig?.name || groupId;
        groupHeader.innerHTML = `<span>📁 ${escapeHtml(groupDisplayName)}</span>`;
        toolsContainer.appendChild(groupHeader);

        groupTools.forEach(tool => {
            toolsContainer.appendChild(createToolElement(tool));
        });
    }
}

function createToolElement(tool) {
    const toolDiv = document.createElement('div');
    toolDiv.className = 'tool-item';

    const providerLabel = tool.provider_name || tool.source_id || 'unknown';
    const secondaryName = tool.display_name && tool.display_name !== tool.name
        ? `<div class="tool-alias">函数名：${escapeHtml(tool.name)}</div>`
        : '';

    toolDiv.innerHTML = `
        <div class="tool-info">
            <div class="tool-name">${escapeHtml(tool.display_name || tool.name)}</div>
            <div class="tool-description">${escapeHtml(tool.description || '暂无描述')}</div>
            <div class="tool-meta">来源：${escapeHtml(providerLabel)} · 类型：${escapeHtml(tool.source_type || 'tool')}</div>
            ${secondaryName}
        </div>
        <label class="tool-toggle">
            <input type="checkbox" ${tool.enabled ? 'checked' : ''} data-tool="${tool.name}">
            <span class="toggle-slider"></span>
        </label>
    `;

    const checkbox = toolDiv.querySelector('input[type="checkbox"]');
    checkbox.addEventListener('change', async (e) => {
        await toggleTool(tool.name, e.target.checked);
    });

    return toolDiv;
}

async function toggleTool(toolName, enabled) {
    try {
        await window.API.updateToolStatus(toolName, enabled);
        await loadTools();
        showToast(`${toolName} ${enabled ? '已启用' : '已禁用'}`, 'success');
    } catch (error) {
        console.error(`Failed to toggle tool ${toolName}:`, error);
        showToast(`切换工具状态失败: ${error.message}`, 'error');

        // 恢复开关状态
        const checkbox = document.querySelector(`input[data-tool="${toolName}"]`);
        if (checkbox) {
            checkbox.checked = !enabled;
        }
    }
}

window.Tools = {
    init: initTools,
    loadTools
};