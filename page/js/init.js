/**
 * 应用初始化模块
 */

// 等待 DOM 加载完成
document.addEventListener('DOMContentLoaded', async () => {
    console.log('DOM loaded, initializing app...');
    
    // 配置 Markdown 渲染引擎
    if (typeof marked !== 'undefined' && typeof hljs !== 'undefined') {
        marked.setOptions({
            gfm: true,          // 启用 GitHub Flavored Markdown
            breaks: true,       // 将换行符转换为 <br>
            highlight: function(code, lang) {
                if (lang && hljs.getLanguage(lang)) {
                    try {
                        return hljs.highlight(code, { language: lang }).value;
                    } catch (e) {
                        console.warn('Highlight error:', e);
                    }
                }
                return hljs.highlightAuto(code).value;
            }
        });
        console.log('Markdown engine configured');
    } else {
        console.warn('Markdown or highlight.js not loaded, using fallback');
    }
    
    try {
        // 初始化 API（获取后端端口）
        const apiReady = await API.init();
        if (!apiReady) {
            showToast('后端服务未就绪，请检查配置', 'error');
            return;
        }
        
        // 设置侧边栏收起/展开
        initSidebarToggle();
        
        // 初始化各个模块
        await initSettings();
        await initPlugins();
        await window.Tools?.init?.();
        await initConversations();
        await initChat();
        await window.Prompts?.init?.();  // 初始化提示词模块
        
        console.log('App initialized successfully');
        
    } catch (error) {
        console.error('Initialization failed:', error);
        showToast(`应用初始化失败：${error.message}`, 'error');
    }
});

// 侧边栏收起/展开功能
function initSidebarToggle() {
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('toggle-sidebar-btn');
    
    console.log('initSidebarToggle:', { sidebar, toggleBtn }); // 调试日志
    
    if (!toggleBtn) {
        console.error('Toggle sidebar button not found!');
        return;
    }
    
    // 从 localStorage 读取状态
    const isCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
    if (isCollapsed) {
        sidebar.classList.add('collapsed');
    }
    
    toggleBtn.addEventListener('click', () => {
        console.log('Toggle button clicked!'); // 调试日志
        sidebar.classList.toggle('collapsed');
        const collapsed = sidebar.classList.contains('collapsed');
        localStorage.setItem('sidebar-collapsed', collapsed);
        console.log('Sidebar collapsed:', collapsed); // 调试日志
    });
}