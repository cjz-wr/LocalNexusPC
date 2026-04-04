/**
 * AI 提示词管理模块
 */

let promptsList = [];
let activePromptId = null;

// 初始化提示词模块
async function initPrompts() {
    await loadPrompts();
    await loadActivePrompt();
    renderPromptsList();
    setupEventListeners();
}

// 加载所有提示词
async function loadPrompts() {
    try {
        const response = await window.API.getSystemPrompts();
        promptsList = response;
    } catch (error) {
        console.error('Failed to load prompts:', error);
        showToast('加载提示词失败', 'error');
    }
}

// 加载当前激活的提示词
async function loadActivePrompt() {
    try {
        const response = await window.API.getActiveSystemPrompt();
        activePromptId = response.id;
    } catch (error) {
        console.error('Failed to load active prompt:', error);
    }
}

// 渲染提示词列表
function renderPromptsList() {
    const container = document.getElementById('prompts-list');
    if (!container) return;
    container.innerHTML = '';

    if (promptsList.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无提示词，点击"新建"创建</div>';
        return;
    }

    promptsList.forEach(prompt => {
        const isActive = activePromptId === prompt.id;
        const promptDiv = document.createElement('div');
        promptDiv.className = `prompt-item ${isActive ? 'active' : ''}`;
        promptDiv.dataset.id = prompt.id;

        promptDiv.innerHTML = `
            <div class="prompt-info">
                <div class="prompt-name">${escapeHtml(prompt.name)}</div>
                <div class="prompt-preview">${escapeHtml(prompt.content.substring(0, 50))}${prompt.content.length > 50 ? '...' : ''}</div>
            </div>
            <div class="prompt-actions">
                <button class="btn-icon set-active" title="设为当前提示词">
                    <svg width="16" height="16" viewBox="0 0 24 24">
                        <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" fill="currentColor"/>
                    </svg>
                </button>
                <button class="btn-icon edit-prompt" title="编辑">
                    <svg width="16" height="16" viewBox="0 0 24 24">
                        <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" fill="currentColor"/>
                    </svg>
                </button>
                <button class="btn-icon delete-prompt" title="删除">
                    <svg width="16" height="16" viewBox="0 0 24 24">
                        <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/>
                    </svg>
                </button>
            </div>
        `;

        // 设为激活
        const setActiveBtn = promptDiv.querySelector('.set-active');
        setActiveBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            setActivePrompt(prompt.id);
        });

        // 编辑
        const editBtn = promptDiv.querySelector('.edit-prompt');
        editBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            openPromptModal(prompt);
        });

        // 删除
        const deleteBtn = promptDiv.querySelector('.delete-prompt');
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            deletePrompt(prompt.id);
        });

        // 点击整个项也可以编辑
        promptDiv.addEventListener('click', () => {
            openPromptModal(prompt);
        });

        container.appendChild(promptDiv);
    });
}

// 设置激活的提示词
async function setActivePrompt(promptId) {
    try {
        await window.API.setActiveSystemPrompt(promptId);
        activePromptId = promptId;
        renderPromptsList();
        showToast('已切换 AI 提示词', 'success');
    } catch (error) {
        console.error('Failed to set active prompt:', error);
        showToast('设置失败', 'error');
    }
}

// 打开新建/编辑模态框
function openPromptModal(prompt = null) {
    const modal = document.getElementById('prompt-edit-modal');
    const form = document.getElementById('prompt-edit-form');
    const nameInput = document.getElementById('prompt-name');
    const contentInput = document.getElementById('prompt-content');
    const modalTitle = modal.querySelector('.modal-header h2');

    if (prompt) {
        modalTitle.textContent = '编辑提示词';
        nameInput.value = prompt.name;
        contentInput.value = prompt.content;
        form.dataset.id = prompt.id;
    } else {
        modalTitle.textContent = '新建提示词';
        nameInput.value = '';
        contentInput.value = '';
        delete form.dataset.id;
    }
    modal.classList.add('show');
}

// 保存提示词（新建或更新）
async function savePrompt() {
    const modal = document.getElementById('prompt-edit-modal');
    const form = document.getElementById('prompt-edit-form');
    const name = document.getElementById('prompt-name').value.trim();
    const content = document.getElementById('prompt-content').value.trim();

    if (!name || !content) {
        showToast('请填写名称和内容', 'error');
        return;
    }

    const id = form.dataset.id;
    let response;
    try {
        if (id) {
            // 更新现有提示词
            response = await window.API.updateSystemPrompt(id, { name, content });
            showToast('提示词已更新', 'success');
        } else {
            // 创建新提示词
            response = await window.API.createSystemPrompt({ name, content });
            showToast('提示词已创建', 'success');
        }
        
        await loadPrompts();
        await loadActivePrompt();
        renderPromptsList();
        modal.classList.remove('show');
    } catch (error) {
        console.error('Failed to save prompt:', error);
        showToast(error.message || '保存失败', 'error');
    }
}

// 删除提示词
async function deletePrompt(promptId) {
    if (!confirm('确定删除此提示词吗？')) return;
    try {
        await window.API.deleteSystemPrompt(promptId);
        if (activePromptId === promptId) {
            activePromptId = null;
        }
        await loadPrompts();
        renderPromptsList();
        showToast('提示词已删除', 'success');
    } catch (error) {
        console.error('Failed to delete prompt:', error);
        showToast('删除失败', 'error');
    }
}

// 设置事件监听
function setupEventListeners() {
    const addBtn = document.getElementById('add-prompt-btn');
    addBtn?.addEventListener('click', () => openPromptModal());

    const saveBtn = document.getElementById('save-prompt-btn');
    saveBtn?.addEventListener('click', savePrompt);

    const modalClose = document.querySelector('#prompt-edit-modal .modal-close');
    modalClose?.addEventListener('click', () => {
        document.getElementById('prompt-edit-modal').classList.remove('show');
    });

    const toggleSidebarBtn = document.getElementById('toggle-prompts-sidebar-btn');
    toggleSidebarBtn?.addEventListener('click', () => {
        const sidebar = document.getElementById('prompts-sidebar');
        sidebar.classList.toggle('collapsed');
        localStorage.setItem('prompts-sidebar-collapsed', sidebar.classList.contains('collapsed'));
    });

    // 从 localStorage 恢复侧边栏状态，仅当 localStorage 中有值时
    const savedState = localStorage.getItem('prompts-sidebar-collapsed');
    if (savedState !== null) {
        if (savedState === 'true') {
            document.getElementById('prompts-sidebar')?.classList.add('collapsed');
        } else {
            document.getElementById('prompts-sidebar')?.classList.remove('collapsed');
        }
    } else {
        // 默认情况下，不折叠侧边栏
        document.getElementById('prompts-sidebar')?.classList.remove('collapsed');
    }
}

// 获取当前激活的提示词内容（供聊天模块使用）
function getActivePromptContent() {
    const activePrompt = promptsList.find(p => p.id === activePromptId);
    return activePrompt ? activePrompt.content : null;
}

window.Prompts = {
    init: initPrompts,
    getActivePromptContent
};

// HTML 转义函数
function escapeHtml(unsafe) {
    if (typeof unsafe !== 'string') return '';
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}