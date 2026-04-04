/**
 * 对话管理模块
 */

let conversations = [];
let currentConversationId = null;

// 初始化对话列表
async function initConversations() {
    const newChatBtn = document.getElementById('new-chat-btn');
    
    // 加载对话列表
    await loadConversations();
    
    // 新建对话按钮
    newChatBtn.addEventListener('click', handleNewConversation);
}

// 加载对话列表
async function loadConversations() {
    try {
        conversations = await API.getConversations();
        console.log('Loaded conversations:', conversations);
        renderConversationList();
        
        // 如果有对话且当前没有选中，选择第一个
        if (conversations.length > 0 && !currentConversationId) {
            selectConversation(conversations[0].id);
        } else if (conversations.length === 0) {
            // 没有对话时自动创建新对话
            await handleNewConversation();
        }
    } catch (error) {
        console.error('Failed to load conversations:', error);
        showToast(`加载对话列表失败：${error.message}`, 'error');
    }
}

// 渲染对话列表
function renderConversationList() {
    const conversationListEl = document.getElementById('conversation-list');
    conversationListEl.innerHTML = '';
    
    if (conversations.length === 0) {
        conversationListEl.innerHTML = '<p style="text-align: center; color: #999; padding: 20px;">暂无对话</p>';
        return;
    }
    
    conversations.forEach(conv => {
        const item = document.createElement('div');
        item.className = 'conversation-item';
        if (conv.id === currentConversationId) {
            item.classList.add('active');
        }
        
        item.innerHTML = `
            <span class="icon">💬</span>
            <span class="conversation-item-title">${escapeHtml(conv.title || '新对话')}</span>
            <button class="delete-conversation-btn" title="删除对话">
                <svg width="16" height="16" viewBox="0 0 24 24">
                    <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/>
                </svg>
            </button>
        `;
        
        // 点击选择对话
        item.addEventListener('click', (e) => {
            if (!e.target.closest('.delete-conversation-btn')) {
                selectConversation(conv.id);
            }
        });
        
        // 删除按钮
        const deleteBtn = item.querySelector('.delete-conversation-btn');
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            handleDeleteConversation(conv.id);
        });
        
        conversationListEl.appendChild(item);
    });
}

// 选择对话
async function selectConversation(conversationId) {
    if (currentConversationId === conversationId) {
        return;
    }
    
    currentConversationId = conversationId;
    
    // 更新 UI 选中状态
    document.querySelectorAll('.conversation-item').forEach(item => {
        item.classList.remove('active');
    });
    const activeItem = document.querySelector(`[data-conversation-id="${conversationId}"]`);
    if (activeItem) {
        activeItem.classList.add('active');
    }
    
    // 重新渲染列表以更新选中状态
    renderConversationList();
    
    // 加载对话消息
    await loadConversationMessages(conversationId);
    
    // 更新标题
    const conv = conversations.find(c => c.id === conversationId);
    if (conv) {
        document.getElementById('chat-title').value = conv.title || '新对话';
    }
}

// 新建对话
async function handleNewConversation() {
    try {
        const result = await API.createConversation();
        console.log('Created conversation:', result);
        
        // 添加到列表
        conversations.unshift({
            id: result.id,
            title: '新对话',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
        });
        
        renderConversationList();
        
        // 选中新对话
        selectConversation(result.id);
        
        // 清空消息区域
        const messagesEl = document.getElementById('messages');
        messagesEl.innerHTML = `
            <div class="message ai-message">
                <div class="message-content">
                    你好！我是你的 AI 助手，有什么可以帮助你的吗？
                </div>
            </div>
        `;
        
        showToast('新对话已创建', 'success');
    } catch (error) {
        console.error('Failed to create conversation:', error);
        showToast(`创建对话失败：${error.message}`, 'error');
    }
}

// 删除对话
async function handleDeleteConversation(conversationId) {
    if (!confirm('确定要删除这个对话吗？')) {
        return;
    }
    
    try {
        await API.deleteConversation(conversationId);
        console.log('Deleted conversation:', conversationId);
        
        // 从列表中移除
        conversations = conversations.filter(c => c.id !== conversationId);
        renderConversationList();
        
        // 如果删除的是当前对话，创建新对话
        if (currentConversationId === conversationId) {
            currentConversationId = null;
            if (conversations.length > 0) {
                selectConversation(conversations[0].id);
            } else {
                await handleNewConversation();
            }
        }
        
        showToast('对话已删除', 'success');
    } catch (error) {
        console.error('Failed to delete conversation:', error);
        showToast(`删除对话失败：${error.message}`, 'error');
    }
}

// 加载对话消息
async function loadConversationMessages(conversationId) {
    try {
        const messages = await API.getConversationMessages(conversationId);
        console.log('Loaded messages:', messages);
        
        renderMessages(messages);
    } catch (error) {
        console.error('Failed to load messages:', error);
        showToast(`加载消息失败：${error.message}`, 'error');
    }
}

// 渲染消息列表
function renderMessages(messages) {
    const messagesEl = document.getElementById('messages');
    if (!messagesEl) return;

    messagesEl.innerHTML = '';

    messages.forEach(msg => {
        const role = msg.role === 'user' ? 'user' : 'ai';
        const content = msg.content || '';
        
        const messageDiv = document.createElement('div');
        messageDiv.className = role === 'user' ? 'message user-message' : 'message ai-message';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = renderMarkdown(content);
        
        messageDiv.appendChild(contentDiv);
        messagesEl.appendChild(messageDiv);
    });
    
    // 加载消息后强制滚动
    scrollToBottom(true);
}

// 添加消息到 UI
function appendMessage(role, content, isUpdating = false) {
    const messagesEl = document.getElementById('messages');
    if (!messagesEl) return null;

    const messageDiv = document.createElement('div');
    messageDiv.className = role === 'user' ? 'message user-message' : 'message ai-message';
    if (isUpdating) {
        messageDiv.setAttribute('data-updating', 'true');
    }

    const contentEl = document.createElement('div');
    contentEl.className = 'message-content';
    contentEl.innerHTML = renderMarkdown(content);

    messageDiv.appendChild(contentEl);
    messagesEl.appendChild(messageDiv);

    // 添加新消息后强制滚动（用户消息或初始 AI 消息）
    scrollToBottom(true);
    return messageDiv;
}

// 更新进行中的消息
function updateMessage(content) {
    const updatingMessage = document.querySelector('[data-updating="true"]');
    if (updatingMessage) {
        const contentEl = updatingMessage.querySelector('.message-content');
        contentEl.innerHTML = renderMarkdown(content);
        // 不传 force，根据 autoScrollEnabled 决定
        scrollToBottom();
    }
}

// 完成消息更新
function finishMessageUpdate() {
    const updatingMessage = document.querySelector('[data-updating="true"]');
    if (updatingMessage) {
        updatingMessage.removeAttribute('data-updating');
        const contentEl = updatingMessage.querySelector('.message-content');
        contentEl.classList.remove('updating');
    }
}

// 滚动到底部，force 参数强制滚动（忽略 autoScrollEnabled 标志）
function scrollToBottom(force = false) {
    const messagesContainer = document.getElementById('messages-container');
    if (!messagesContainer) return;
    if (force || window.autoScrollEnabled) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

// HTML 转义
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 更新当前对话标题
async function updateCurrentTitle(newTitle) {
    if (!currentConversationId) {
        return;
    }
    
    try {
        await API.updateConversationTitle(currentConversationId, newTitle);
        
        // 更新本地列表
        const conv = conversations.find(c => c.id === currentConversationId);
        if (conv) {
            conv.title = newTitle;
        }
        
        renderConversationList();
    } catch (error) {
        console.error('Failed to update title:', error);
    }
}

// 清空当前对话
async function clearCurrentMessages() {
    const conversationId = getCurrentConversationId();
    if (!conversationId) {
        showToast('没有活动的对话', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/clear`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error(`清除对话失败: ${response.status}`);

        const messagesEl = document.getElementById('messages');
        messagesEl.innerHTML = `<div class="message ai-message"><div class="message-content">对话已清空</div></div>`;
        // 清空后强制滚动
        scrollToBottom(true);
        showToast('对话已清空', 'success');
    } catch (error) {
        console.error('Error clearing messages:', error);
        showToast('清除对话失败', 'error');
    }
}

// 获取当前对话 ID
function getCurrentConversationId() {
    return currentConversationId;
}
