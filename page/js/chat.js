/**
 * 聊天功能模块
 */

let isSending = false;

// 全局滚动控制标志，用于控制是否自动滚动到底部
window.autoScrollEnabled = true;

// 初始化聊天功能
async function initChat() {
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-btn');
    const chatTitleInput = document.getElementById('chat-title');
    const clearMessagesBtn = document.getElementById('clear-messages-btn');
    const messagesContainer = document.getElementById('messages-container');
    
    // 添加滚动监听，控制自动滚动标志
    messagesContainer.addEventListener('scroll', () => {
        const { scrollTop, scrollHeight, clientHeight } = messagesContainer;
        // 当滚动条距离底部小于 10px 时，认为用户希望自动滚动
        const isNearBottom = scrollHeight - scrollTop - clientHeight <= 10;
        window.autoScrollEnabled = isNearBottom;
    });
    
    // 发送消息按钮
    sendBtn.addEventListener('click', handleSendMessage);
    
    // 输入框回车发送
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    });
    
    // 自动调整文本框高度
    messageInput.addEventListener('input', () => {
        autoResizeTextarea(messageInput);
    });
    
    // 标题编辑（防抖）
    const debouncedTitleUpdate = debounce((newTitle) => {
        updateCurrentTitle(newTitle);
    }, 1000);
    
    chatTitleInput.addEventListener('input', (e) => {
        debouncedTitleUpdate(e.target.value.trim());
    });
    
    // 清空对话按钮
    clearMessagesBtn.addEventListener('click', clearCurrentMessages);
}

// 处理发送消息
async function handleSendMessage() {
    if (isSending) return;
    
    const messageInput = document.getElementById('message-input');
    const message = messageInput.value.trim();
    if (!message || !getCurrentConversationId()) return;
    
    isSending = true;
    const sendBtn = document.getElementById('send-btn');
    sendBtn.disabled = true;
    
    // 发送消息前强制滚动到底部并启用自动滚动
    window.autoScrollEnabled = true;
    scrollToBottom(true);  // 注意：scrollToBottom 来自 conversation.js
    
    try {
        // 添加用户消息到 UI
        appendMessage('user', message);
        
        // 清空输入框
        messageInput.value = '';
        autoResizeTextarea(messageInput);
        
        // 创建 AI 消息占位符
        let aiResponseContent = '';
        appendMessage('ai', '', true);
        
        // 流式请求 AI 响应
        await API.streamChat(
            getCurrentConversationId(),
            message,
            {
                onStart: (data) => {
                    console.log('Stream started:', data);
                },
                onToken: (token) => {
                    console.log('Received token:', token);
                    aiResponseContent += token;
                    updateMessage(aiResponseContent);
                },
                onToolCallStart: (data) => {
                    const toolCalls = data.tool_calls || [];
                    toolCalls.forEach((toolCall) => {
                        let args = toolCall.function?.arguments || '';
                        try {
                            args = JSON.parse(args);
                        } catch {
                            // 保持原始字符串即可
                        }
                        showToolStatus(toolCall.function?.name || 'unknown', 'running', args);
                    });
                },
                onToolCallResult: (data) => {
                    showToolStatus(
                        data.tool_name || 'unknown',
                        data.error ? 'failed' : 'completed',
                        data.error || data.result || ''
                    );
                },
                onComplete: (data) => {
                    console.log('Stream completed:', data);
                    finishMessageUpdate();
                    
                    // 重新加载消息列表以同步状态
                    loadConversationMessages(getCurrentConversationId());
                    
                    isSending = false;
                    sendBtn.disabled = false;
                },
                onError: (error) => {
                    console.error('Stream error:', error);
                    finishMessageUpdate();
                    showToast(`AI 响应失败：${error.message}`, 'error');
                    
                    isSending = false;
                    sendBtn.disabled = false;
                },
            }
        );
        
    } catch (error) {
        console.error('Failed to send message:', error);
        showToast(`发送消息失败：${error.message}`, 'error');
        
        isSending = false;
        sendBtn.disabled = false;
    }
}

// 显示工具调用状态
function showToolStatus(toolName, status, data) {
    const messagesContainer = document.getElementById('messages');
    if (!messagesContainer) {
        return;
    }

    const statusDiv = document.createElement('div');
    statusDiv.className = `message system-message tool-status-${status}`;

    const serializedData = typeof data === 'string'
        ? data
        : (data == null ? '' : JSON.stringify(data, null, 2));
    const shortenedData = serializedData.length > 400 ? `${serializedData.substring(0, 400)}...` : serializedData;

    let contentHtml = '';
    if (status === 'running') {
        contentHtml = `
            <div class="message-content" style="background-color: #f0f0f0; color: #666; font-size: 12px;">
                🔧 正在调用工具：${escapeHtml(toolName)}
                ${shortenedData ? `<br><pre style="max-width: 500px; overflow-x: auto; margin-top: 4px; white-space: pre-wrap;">${escapeHtml(shortenedData)}</pre>` : ''}
            </div>
        `;
    } else if (status === 'completed') {
        contentHtml = `
            <div class="message-content" style="background-color: #f0f0f0; color: #666; font-size: 12px;">
                ✅ 工具 ${escapeHtml(toolName)} 返回：<br>
                <pre style="max-width: 500px; overflow-x: auto; margin-top: 4px; white-space: pre-wrap;">${escapeHtml(shortenedData)}</pre>
            </div>
        `;
    } else if (status === 'failed') {
        contentHtml = `
            <div class="message-content" style="background-color: #fff1f0; color: #a8071a; font-size: 12px;">
                ⚠️ 工具 ${escapeHtml(toolName)} 执行失败：<br>
                <pre style="max-width: 500px; overflow-x: auto; margin-top: 4px; white-space: pre-wrap;">${escapeHtml(shortenedData)}</pre>
            </div>
        `;
    }

    statusDiv.innerHTML = contentHtml;
    messagesContainer.appendChild(statusDiv);
    scrollToBottom();

    if (status !== 'running') {
        setTimeout(() => {
            statusDiv.remove();
        }, 5000);
    }
}

