/**
 * 工具函数模块
 */

// 生成 UUID
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// 格式化时间
function formatTime(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    // 小于 1 分钟
    if (diff < 60000) {
        return '刚刚';
    }
    // 小于 1 小时
    if (diff < 3600000) {
        return `${Math.floor(diff / 60000)}分钟前`;
    }
    // 小于 24 小时
    if (diff < 86400000) {
        return `${Math.floor(diff / 3600000)}小时前`;
    }
    // 小于 7 天
    if (diff < 604800000) {
        return `${Math.floor(diff / 86400000)}天前`;
    }
    
    // 超过 7 天显示具体日期
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    
    if (year === now.getFullYear()) {
        return `${month}-${day} ${hours}:${minutes}`;
    }
    return `${year}-${month}-${day} ${hours}:${minutes}`;
}

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 自动调整文本框高度
function autoResizeTextarea(textarea) {
    textarea.style.height = 'auto';
    const newHeight = Math.min(textarea.scrollHeight, 200);
    textarea.style.height = `${newHeight}px`;
}

// 显示 Toast 通知
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Markdown 渲染（使用 marked 库）
function renderMarkdown(text) {
    if (!text) return '';

    // 如果 marked 库可用，使用其解析
    if (typeof marked !== 'undefined') {
        try {
            // 配置 marked 选项（在 init.js 中统一配置，此处确保已配置）
            // 直接调用 marked 函数同步返回 HTML
            return marked.parse(text);
        } catch (e) {
            console.error('Markdown parse error:', e);
            // 降级为转义 + 换行
            return escapeHtml(text).replace(/\n/g, '<br>');
        }
    } else {
        // 降级：仅转义 HTML 并保留换行
        return escapeHtml(text).replace(/\n/g, '<br>');
    }
}

// HTML 转义辅助函数
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 代码块高亮（简单版本）
function highlightCode(text) {
    return text.replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
        return `<pre><code class="language-${lang}">${code}</code></pre>`;
    });
}

// 等待 DOM 加载完成
function waitForDOM(callback) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', callback);
    } else {
        callback();
    }
}

// 检查元素是否存在
function elementExists(selector) {
    return document.querySelector(selector) !== null;
}
