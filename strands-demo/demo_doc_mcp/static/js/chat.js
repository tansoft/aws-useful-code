document.addEventListener('DOMContentLoaded', function () {
    const chatMessages = document.getElementById('chatMessages');
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');
    const sessionManagerBtn = document.getElementById('sessionManagerBtn');
    const createSessionBtn = document.getElementById('createSessionBtn');
    const clearAllSessionsBtn = document.getElementById('clearAllSessionsBtn');
    const sessionsContainer = document.getElementById('sessionsContainer');
    const roleSelectBtn = document.getElementById('roleSelectBtn');
    const currentRoleIcon = document.getElementById('currentRoleIcon');
    const currentRoleName = document.getElementById('currentRoleName');
    const roleList = document.getElementById('roleList');
    const systemPromptEditor = document.getElementById('systemPromptEditor');
    const resetPromptBtn = document.getElementById('resetPromptBtn');
    const mcpSelection = document.getElementById('mcpSelection');
    const imageUploadBtn = document.getElementById('imageUploadBtn');
    const imageUploadInput = document.getElementById('imageUploadInput');
    const imagePreviewContainer = document.getElementById('imagePreviewContainer');
    const imagePreview = document.getElementById('imagePreview');
    const removeImageBtn = document.getElementById('removeImageBtn');

    let currentImageData = null;
    let currentImageType = null;
    let currentSessionId = localStorage.getItem('currentSessionId') || null;
    let sessions = [];
    let chatHistory = {};
    let availableRoles = [];
    let currentRole = null;
    let originalPrompt = '';  // 当前角色默认提示词
    let sessionPrompt = '';   // 会话级别自定义提示词
    let rolePromptsCache = {};  // 缓存各个角色的默认提示词
    let availableMcps = [];
    let selectedMcps = [];

    const sessionModal = new bootstrap.Modal(document.getElementById('sessionModal'));
    const roleModal = new bootstrap.Modal(document.getElementById('roleModal'));
    const imageModal = new bootstrap.Modal(document.getElementById('imageModal'));
    
    // SHA-256 哈希函数
    async function sha256(message) {
        // 将字符串转换为 Uint8Array
        const msgBuffer = new TextEncoder().encode(message);
        
        // 使用 SubtleCrypto API 计算哈希值
        const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
        
        // 将 ArrayBuffer 转换为十六进制字符串
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        
        return hashHex;
    }
    
    function loadSessionsFromLocalStorage() {
        try {
            const savedSessions = localStorage.getItem('sessions');
            if (savedSessions) sessions = JSON.parse(savedSessions);

            const savedChatHistory = localStorage.getItem('chatHistory');
            if (savedChatHistory) chatHistory = JSON.parse(savedChatHistory);

            renderSessions();

            if (currentSessionId && chatHistory[currentSessionId]) {
                loadSessionChat(currentSessionId);
            }
        } catch (error) {
            console.error('Error loading sessions from localStorage:', error);
        }
    }
    
    function saveSessionsToLocalStorage() {
        try {
            localStorage.setItem('sessions', JSON.stringify(sessions));
            localStorage.setItem('chatHistory', JSON.stringify(chatHistory));
        } catch (error) {
            console.error('Error saving sessions to localStorage:', error);
        }
    }


    // 会话配置的本地存储管理（包含角色、自定义提示词、MCP选择）
    function saveSessionConfig(sessionId, config) {
        try {
            const sessionConfigs = JSON.parse(localStorage.getItem('sessionConfigs') || '{}');
            sessionConfigs[sessionId] = {
                roleId: config.roleId || (currentRole ? currentRole.id : null),
                customPrompt: config.customPrompt || null,
                selectedMcps: config.selectedMcps || null,
                lastUpdated: new Date().toISOString()
            };
            localStorage.setItem('sessionConfigs', JSON.stringify(sessionConfigs));
        } catch (error) {
            console.error('Error saving session config:', error);
        }
    }

    function getSessionConfig(sessionId) {
        try {
            const sessionConfigs = JSON.parse(localStorage.getItem('sessionConfigs') || '{}');
            return sessionConfigs[sessionId] || {};
        } catch (error) {
            console.error('Error loading session config:', error);
            return {};
        }
    }

    function deleteSessionConfig(sessionId) {
        try {
            const sessionConfigs = JSON.parse(localStorage.getItem('sessionConfigs') || '{}');
            delete sessionConfigs[sessionId];
            localStorage.setItem('sessionConfigs', JSON.stringify(sessionConfigs));
        } catch (error) {
            console.error('Error deleting session config:', error);
        }
    }
    
    // 初始化应用 - 确保正确的加载顺序
    async function initializeApp() {
        try {
            loadSessionsFromLocalStorage();

            // 首先加载角色和MCP数据
            await Promise.all([
                loadAvailableRoles(),
                loadAvailableMcps()
            ]);

            // 然后加载当前会话的角色配置
            await loadCurrentRoleFromSession();
        } catch (error) {
            console.error('Error initializing app:', error);
        }
    }

    // 启动应用初始化
    initializeApp();

    // 角色管理相关函数
    async function loadAvailableRoles() {
        try {
            const urlParams = new URLSearchParams(window.location.search);
            const token = urlParams.get('token');
            if (!token) return;

            // const hash = await sha256('');
            const response = await fetch(`/api/roles?token=${token}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-amz-content-sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', // fixed for empty string
                }
            });

            if (!response.ok) {
                console.error(`Error fetching roles: ${response.status} ${response.statusText}`);
                const responseText = await response.text();
                console.error('Response body:', responseText);
                return;
            }

            const data = await response.json();
            availableRoles = data.roles;
            renderRoleList();

            // 如果还没有选择角色，设置默认角色
            if (!currentRole && availableRoles.length > 0) {
                const defaultRole = availableRoles.find(r => r.id === 'aws_architect') || availableRoles[0];
                currentRole = defaultRole;
                updateCurrentRoleDisplay();
                resetMcpSelectionToDefault();
                renderRoleList();

                // 获取并缓存默认角色的提示词
                const defaultPrompt = await getRoleDefaultPrompt(defaultRole.id);
                if (defaultPrompt) {
                    originalPrompt = defaultPrompt;
                    systemPromptEditor.value = defaultPrompt;
                }
            }
        } catch (error) {
            console.error('Error loading roles:', error);
        }
    }

    function renderRoleList() {
        if (availableRoles.length === 0) {
            roleList.innerHTML = '<div class="text-center p-3 text-muted">没有可用角色</div>';
            return;
        }

        let html = '';
        availableRoles.forEach(role => {
            const isActive = currentRole && currentRole.id === role.id;
            html += `
            <div class="list-group-item role-item ${isActive ? 'active' : ''}" data-role-id="${role.id}">
                <div class="d-flex align-items-center">
                    <i class="${role.icon} me-2" style="font-size: 24px;"></i>
                    <div class="flex-grow-1">
                        <div class="fw-medium">${role.name}</div>
                        <small class="text-muted">${role.description}</small>
                    </div>
                    ${isActive ? '<i class="bi bi-check-circle-fill text-success"></i>' : ''}
                </div>
            </div>
            `;
        });

        roleList.innerHTML = html;

        // 为角色项添加点击事件
        document.querySelectorAll('.role-item').forEach(item => {
            item.addEventListener('click', function() {
                selectRole(this.dataset.roleId);
            });
        });
    }

    async function selectRole(roleId) {
        try {
            const role = availableRoles.find(r => r.id === roleId);
            if (!role) return;

            currentRole = role;
            updateCurrentRoleDisplay();

            // 加载角色的系统提示词
            await loadRolePrompt(roleId, true);

            // 重置MCP选择为角色默认配置
            resetMcpSelectionToDefault();

            // 重新渲染角色列表以显示选中状态
            renderRoleList();
            renderMcpSelection();

            // 如果有当前会话，更新会话的角色信息并保存配置
            if (currentSessionId) {
                updateSessionRole(currentSessionId, roleId);
                saveCurrentSessionConfig(); // 保存角色切换后的配置
            }

        } catch (error) {
            console.error('Error selecting role:', error);
        }
    }

    async function loadRolePrompt(roleId, forceReload = false) {
        try {
            const urlParams = new URLSearchParams(window.location.search);
            const token = urlParams.get('token');
            if (!token) return;

            const response = await fetch(`/api/roles/${roleId}?token=${token}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-amz-content-sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
                }
            });

            if (!response.ok) {
                console.error(`Error fetching role ${roleId}: ${response.status} ${response.statusText}`);
                const responseText = await response.text();
                console.error('Response body:', responseText);
                return;
            }

            const roleData = await response.json();

            originalPrompt = roleData.system_prompt;
            // 缓存角色的默认提示词
            rolePromptsCache[roleId] = roleData.system_prompt;

            // 根据不同场景更新提示词内容
            if (forceReload) {
                // 强制重新加载：使用角色默认提示词，清除会话自定义提示词
                systemPromptEditor.value = originalPrompt;
                sessionPrompt = '';
            } else {
                // 正常加载：如果有会话级别的自定义提示词，显示它；否则显示角色默认提示词
                systemPromptEditor.value = sessionPrompt || originalPrompt;
            }

            // 不再有全局编辑限制，用户可以自由修改当前会话的提示词
            systemPromptEditor.readOnly = false;

        } catch (error) {
            console.error('Error loading role prompt:', error);
        }
    }

    // 获取角色默认提示词（优先从缓存）
    async function getRoleDefaultPrompt(roleId) {
        // 首先检查缓存
        if (rolePromptsCache[roleId]) {
            return rolePromptsCache[roleId];
        }

        // 如果缓存中没有，从服务器获取
        try {
            const urlParams = new URLSearchParams(window.location.search);
            const token = urlParams.get('token');
            if (!token) return null;

            const response = await fetch(`/api/roles/${roleId}?token=${token}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-amz-content-sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
                }
            });

            if (!response.ok) {
                console.error(`Error fetching role ${roleId}: ${response.status} ${response.statusText}`);
                return null;
            }

            const roleData = await response.json();
            const defaultPrompt = roleData.system_prompt;

            // 缓存结果
            rolePromptsCache[roleId] = defaultPrompt;

            return defaultPrompt;
        } catch (error) {
            console.error('Error getting role default prompt:', error);
            return null;
        }
    }

    function updateCurrentRoleDisplay() {
        if (currentRole) {
            currentRoleIcon.className = `${currentRole.icon}`;
            currentRoleIcon.title = currentRole.name;
            currentRoleName.textContent = currentRole.name;
            document.title = currentRole.name;  // 更新页面标题
        }
    }

    async function loadCurrentRoleFromSession() {
        if (!currentSessionId) {
            // 如果没有当前会话，创建第一个默认会话
            if (sessions.length === 0) {
                const defaultRole = availableRoles.find(r => r.id === 'aws_architect') || availableRoles[0];
                if (defaultRole) {
                    currentRole = defaultRole;
                    updateCurrentRoleDisplay();
                    resetMcpSelectionToDefault();
                    renderRoleList();
                    renderMcpSelection();

                    // 创建第一个会话
                    createNewSession(true);
                }
                return;
            } else {
                // 如果有会话但没有当前会话ID，选择第一个会话
                currentSessionId = sessions[0].id;
                localStorage.setItem('currentSessionId', currentSessionId);
            }
        }

        // 加载当前会话的角色配置
        await loadSessionRole(currentSessionId);

        // 加载会话的聊天记录
        loadSessionChat(currentSessionId);
    }

    // MCP管理相关函数
    async function loadAvailableMcps() {
        try {
            const urlParams = new URLSearchParams(window.location.search);
            const token = urlParams.get('token');
            if (!token) return;

            const response = await fetch(`/api/mcps?token=${token}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-amz-content-sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
                }
            });

            if (!response.ok) {
                console.error(`Error fetching MCPs: ${response.status} ${response.statusText}`);
                const responseText = await response.text();
                console.error('Response body:', responseText);
                return;
            }

            const data = await response.json();
            availableMcps = data.mcps;
            renderMcpSelection();
        } catch (error) {
            console.error('Error loading MCPs:', error);
        }
    }

    function renderMcpSelection() {
        if (availableMcps.length === 0) {
            mcpSelection.innerHTML = '<div class="text-center p-3 text-muted">没有可用的MCP工具</div>';
            return;
        }

        let html = '';
        availableMcps.forEach(mcp => {
            const isSelected = selectedMcps.includes(mcp.id);
            const isDefault = currentRole && currentRole.mcp_configs && currentRole.mcp_configs.some(config => config.id === mcp.id);

            html += `
            <div class="list-group-item mcp-item ${isSelected ? 'active' : ''}" data-mcp-id="${mcp.id}">
                <div class="d-flex align-items-center">
                    <input class="form-check-input me-2" type="checkbox" ${isSelected ? 'checked' : ''} data-mcp-id="${mcp.id}">
                    <div class="flex-grow-1">
                        <div class="fw-medium">${mcp.name}</div>
                        <small class="text-muted">${mcp.description}</small>
                        ${isDefault ? '<small class="badge bg-primary ms-1">默认</small>' : ''}
                    </div>
                </div>
            </div>
            `;
        });

        mcpSelection.innerHTML = html;

        // 为MCP项添加点击事件
        document.querySelectorAll('.mcp-item').forEach(item => {
            item.addEventListener('click', function() {
                const mcpId = this.dataset.mcpId;
                const checkbox = this.querySelector('input[type="checkbox"]');
                const isCurrentlySelected = selectedMcps.includes(mcpId);

                if (isCurrentlySelected) {
                    selectedMcps = selectedMcps.filter(id => id !== mcpId);
                    checkbox.checked = false;
                    this.classList.remove('active');
                } else {
                    selectedMcps.push(mcpId);
                    checkbox.checked = true;
                    this.classList.add('active');
                }

                console.log('Selected MCPs:', selectedMcps);
                saveCurrentSessionConfig();
            });
        });
    }

    function resetMcpSelectionToDefault() {
        if (currentRole && currentRole.mcp_configs) {
            selectedMcps = currentRole.mcp_configs.map(config => config.id);
        } else {
            selectedMcps = [];
        }
        renderMcpSelection();
    }

    function updateSessionRole(sessionId, roleId) {
        // 更新本地会话数据中的角色信息
        const session = sessions.find(s => s.id === sessionId);
        if (session) {
            session.role_id = roleId;
            saveSessionsToLocalStorage();
        }
    }

    function addUserMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        messageDiv.innerHTML = `
            <div class="message-content">
                ${text}
                <button class="copy-message-btn" title="复制消息" data-message="${text.replace(/"/g, '&quot;')}">
                    <svg viewBox="0 0 16 16" fill="currentColor">
                        <path d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1v-1z"/>
                        <path d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5h3zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3z"/>
                    </svg>
                </button>
            </div>
        `;
        chatMessages.appendChild(messageDiv);
        scrollToBottom();

        const copyBtn = messageDiv.querySelector('.copy-message-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', handleMessageCopy);
        }
    }

    function addBotMessage(text, id = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message';
        if (id) messageDiv.id = id;

        const processedText = processAnswerTags(text);
        messageDiv.innerHTML = `<div class="message-content markdown-content">${marked.parse(processedText)}</div>`;
        chatMessages.appendChild(messageDiv);

        addCopyFunctionalityToAnswerBlocks(messageDiv);
        addCopyFunctionalityToCodeBlocks(messageDiv);
        // 为机器人消息中的图片添加点击事件
        addImageClickHandlers(messageDiv);
        scrollToBottom();
        return messageDiv;
    }

    function processAnswerTags(text) {
        return text.replace(/<answer>([\s\S]*?)<\/answer>/g, (match, content) => {
            const answerId = 'answer-' + Math.random().toString(36).substr(2, 9);
            return `<div class="answer-block" data-answer-id="${answerId}">
                ${content.trim()}
                <button class="copy-answer-btn" data-answer-id="${answerId}" title="复制答案">
                    <svg viewBox="0 0 16 16" fill="currentColor">
                        <path d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1v-1z"/>
                        <path d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5h3zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3z"/>
                    </svg>
                </button>
            </div>`;
        });
    }

    // 为 answer 块添加复制功能
    function addCopyFunctionalityToAnswerBlocks(container) {
        container.querySelectorAll('.copy-answer-btn').forEach(button => {
            button.addEventListener('click', handleAnswerCopy);
        });
    }

    // 获取 answer 块的纯文本内容
    function getAnswerTextContent(answerBlock) {
        // 创建一个临时克隆，移除复制按钮
        const clone = answerBlock.cloneNode(true);
        const copyBtn = clone.querySelector('.copy-answer-btn');
        if (copyBtn) {
            copyBtn.remove();
        }

        // 返回纯文本内容
        return clone.textContent || clone.innerText || '';
    }

    // 统一的复制到剪贴板函数
    function copyToClipboard(text, buttonElement = null, showNotification = true) {
        const cleanText = text.trim();

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(cleanText).then(() => {
                if (buttonElement) showCopyFeedback(buttonElement, '已复制!', true);
                if (showNotification) showCopyNotification('已复制');
            }).catch(err => {
                console.error('复制失败:', err);
                const success = fallbackCopyTextToClipboard(cleanText);
                if (buttonElement) showCopyFeedback(buttonElement, success ? '已复制!' : '复制失败', success);
                if (showNotification) showCopyNotification(success ? '已复制' : '复制失败', success);
            });
        } else {
            const success = fallbackCopyTextToClipboard(cleanText);
            if (buttonElement) showCopyFeedback(buttonElement, success ? '已复制!' : '复制失败', success);
            if (showNotification) showCopyNotification(success ? '已复制' : '复制失败', success);
        }
    }

    // 统一的复制反馈函数
    function showCopyFeedback(buttonElement, message, isSuccess) {
        const originalText = buttonElement.innerHTML;
        const originalColor = buttonElement.style.color;

        // 更新按钮为成功图标
        buttonElement.innerHTML = `
            <svg viewBox="0 0 16 16" fill="currentColor">
                <path d="M13.854 3.646a.5.5 0 0 1 0 .708l-7 7a.5.5 0 0 1-.708 0l-3.5-3.5a.5.5 0 1 1 .708-.708L6.5 10.293l6.646-6.647a.5.5 0 0 1 .708 0z"/>
            </svg>
        `;
        buttonElement.style.color = isSuccess ? '#28a745' : '#dc3545';

        // 1.5秒后恢复原状
        setTimeout(() => {
            buttonElement.innerHTML = originalText;
            buttonElement.style.color = originalColor;
        }, 1500);

        // 同时显示全局通知
        showCopyNotification(message, isSuccess);
    }

    // 添加加载指示器
    function addLoadingIndicator() {
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'loading bot-message';
        loadingDiv.id = 'loadingIndicator';
        loadingDiv.innerHTML = `
            <div class="message-content">
                <div class="loading-dots">
                    <div></div>
                    <div></div>
                    <div></div>
                </div>
            </div>
        `;
        chatMessages.appendChild(loadingDiv);
        scrollToBottom();
    }

    // 移除加载指示器
    function removeLoadingIndicator() {
        const loadingIndicator = document.getElementById('loadingIndicator');
        if (loadingIndicator) {
            loadingIndicator.remove();
        }
    }

    // 滚动到底部
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // 将对话内容保存到指定会话的历史记录中
    function saveChatToHistory() {
        if (!currentSessionId) return;
        
        // 获取当前聊天消息
        const messages = [];
        document.querySelectorAll('.message').forEach(msg => {
            const isUser = msg.classList.contains('user-message');
            const messageContent = msg.querySelector('.message-content');

            let content;
            if (isUser) {
                // 对于用户消息，只保存文本内容，不包括复制按钮
                const copyBtn = messageContent.querySelector('.copy-message-btn');
                const contentClone = messageContent.cloneNode(true);
                const clonedCopyBtn = contentClone.querySelector('.copy-message-btn');
                if (clonedCopyBtn) {
                    clonedCopyBtn.remove();
                }
                content = contentClone.innerHTML.trim();
            } else {
                // 对于机器人消息，保存完整内容
                content = messageContent.innerHTML;
            }

            messages.push({
                role: isUser ? 'user' : 'assistant',
                content: content,
                timestamp: new Date().toISOString()
            });
        });
        
        // 保存到会话历史
        chatHistory[currentSessionId] = messages;
        
        // 保存到 localStorage
        saveSessionsToLocalStorage();
    }
    
    // 加载指定会话的聊天记录
    function loadSessionChat(sessionId) {
        if (!sessionId || !chatHistory[sessionId]) {
            // 新会话或没有历史记录，显示默认欢迎消息
            chatMessages.innerHTML = '';
            addBotMessage('<p>你好，我是AWS解决方案架构师！👋 </p><p>你可以问我任何AWS的问题，比如：EC2的带宽是多少？Lambda的最大运行时间？</p><p>💡 <strong>提示</strong>：点击左上角的AWS图标可以切换到其他AI助手角色。</p>');
            return;
        }
        
        // 清空当前聊天区域
        chatMessages.innerHTML = '';
        
        // 加载历史消息
        const messages = chatHistory[sessionId];
        messages.forEach(msg => {
            if (msg.role === 'user') {
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message user-message';

                // 清理历史消息中可能包含的复制按钮HTML
                let cleanContent = msg.content;
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = cleanContent;

                // 移除可能存在的复制按钮
                const existingCopyBtn = tempDiv.querySelector('.copy-message-btn');
                if (existingCopyBtn) {
                    existingCopyBtn.remove();
                    cleanContent = tempDiv.innerHTML;
                }

                // 提取纯文本内容（去除HTML标签）
                const plainTextContent = tempDiv.textContent || tempDiv.innerText || '';

                messageDiv.innerHTML = `
                    <div class="message-content">
                        ${cleanContent}
                        <button class="copy-message-btn" title="复制消息">
                            <svg viewBox="0 0 16 16" fill="currentColor">
                                <path d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1v-1z"/>
                                <path d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5h3zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3z"/>
                            </svg>
                        </button>
                    </div>
                `;
                chatMessages.appendChild(messageDiv);

                // 为历史消息的复制按钮添加事件监听器
                const copyBtn = messageDiv.querySelector('.copy-message-btn');
                if (copyBtn) {
                    copyBtn.dataset.message = plainTextContent;
                    copyBtn.addEventListener('click', handleMessageCopy);
                }

                // 为历史用户消息中的图片添加点击事件
                addImageClickHandlers(messageDiv);
            } else {
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message bot-message';

                // 处理历史消息中的 <answer> 标签
                const processedContent = processAnswerTags(msg.content);

                messageDiv.innerHTML = `
                    <div class="message-content markdown-content">
                        ${processedContent}
                    </div>
                `;
                chatMessages.appendChild(messageDiv);

                // 为历史消息中的 answer 块和代码块添加复制功能
                addCopyFunctionalityToAnswerBlocks(messageDiv);
                addCopyFunctionalityToCodeBlocks(messageDiv);
                // 为历史消息中的图片添加点击事件
                addImageClickHandlers(messageDiv);
            }
        });
        
        // 滚动到底部
        scrollToBottom();
    }
    
    // 渲染会话列表到模态框
    function renderSessions() {
        if (sessions.length === 0) {
            sessionsContainer.innerHTML = `<div class="text-center p-3 text-muted">没有可用的会话，点击"新建会话"按钮创建一个新的会话。</div>`;
            return;
        }
        
        let html = '';
        sessions.forEach(session => {
            const isActive = session.id === currentSessionId;
            const date = session.created_at ? new Date(session.created_at).toLocaleString() : '无时间信息';
            const title = session.title || `会话 ${session.id.substring(0, 8)}...`;
            
            html += `
            <div class="list-group-item session-item ${isActive ? 'active' : ''}" data-session-id="${session.id}">
                <div>
                    <div>${title}</div>
                    <small class="text-muted">${date}</small>
                </div>
                <button class="btn btn-sm btn-outline-danger delete-session-btn" data-session-id="${session.id}">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
            `;
        });
        
        sessionsContainer.innerHTML = html;
        
        // 为会话项添加事件监听
        document.querySelectorAll('.session-item').forEach(item => {
            item.addEventListener('click', function(e) {
                if (!e.target.closest('.delete-session-btn')) {
                    selectSession(this.dataset.sessionId);
                }
            });
        });
        
        // 为删除按钮添加事件监听
        document.querySelectorAll('.delete-session-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                deleteSession(this.dataset.sessionId);
            });
        });
    }
    
    // 生成UUID
    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    // 创建新会话的通用函数
    function createNewSession(isFirstSession = false) {
        // 先保存当前会话的配置（如果不是第一个会话）
        if (!isFirstSession && currentSessionId) {
            saveChatToHistory();
            saveCurrentSessionConfig();
        }

        const sessionId = generateUUID();

        // 使用当前用户选择的角色创建新会话
        const newSession = {
            id: sessionId,
            title: '新会话',
            created_at: new Date().toISOString(),
            role_id: currentRole ? currentRole.id : 'aws_architect'
        };

        // 添加到会话列表
        sessions.push(newSession);
        chatHistory[sessionId] = [];

        // 设置为当前会话
        currentSessionId = sessionId;
        localStorage.setItem('currentSessionId', sessionId);

        // 重置为当前角色的默认配置
        resetMcpSelectionToDefault();
        if (currentRole) {
            systemPromptEditor.value = originalPrompt;
            sessionPrompt = '';
        }

        // 保存新会话的初始配置
        saveCurrentSessionConfig();
        saveSessionsToLocalStorage();

        // 显示欢迎消息
        chatMessages.innerHTML = '';
        addBotMessage('<p>你好，我是AWS解决方案架构师！👋 </p><p>你可以问我任何AWS的问题，比如：EC2的带宽是多少？Lambda的最大运行时间？</p><p>💡 <strong>提示</strong>：点击左上角的AWS图标可以切换到其他AI助手角色。</p>');
        saveChatToHistory();

        return sessionId;
    }
    
    // 创建一个新会话
    function createSession() {
        createNewSession();

        // 关闭模态框
        sessionModal.hide();

        // 更新会话列表
        renderSessions();
    }
    
    // 选择会话
    async function selectSession(sessionId) {
        // 如果是当前会话，则不做切换
        if (sessionId === currentSessionId) {
            sessionModal.hide();
            return;
        }

        // 保存当前会话的配置到本地存储
        if (currentSessionId) {
            saveChatToHistory();
            saveCurrentSessionConfig();
        }

        // 更新当前会话 ID
        currentSessionId = sessionId;
        localStorage.setItem('currentSessionId', sessionId);

        // 加载会话的角色配置
        await loadSessionRole(sessionId);

        // 加载选中会话的聊天记录
        loadSessionChat(sessionId);

        // 关闭模态框
        sessionModal.hide();

        // 更新会话列表（高亮当前选中项）
        renderSessions();
    }

    // 保存当前会话的完整配置（角色+自定义提示词+MCP）
    function saveCurrentSessionConfig() {
        if (!currentSessionId) return;

        const currentPrompt = systemPromptEditor.value.trim();
        const isCustomPrompt = currentPrompt !== originalPrompt;

        const sessionConfig = {
            roleId: currentRole ? currentRole.id : null,
            customPrompt: isCustomPrompt ? currentPrompt : null,
            selectedMcps: [...selectedMcps]  // 保存用户选择的MCP列表，包括空数组
        };
        saveSessionConfig(currentSessionId, sessionConfig);
    }

    async function loadSessionRole(sessionId) {
        console.log('Loading session role for session:', sessionId);

        // 从本地存储加载完整的会话配置
        const sessionConfig = getSessionConfig(sessionId);
        console.log('Session config loaded:', sessionConfig);

        // 优先使用会话配置中的角色，如果没有则使用会话数据中的角色
        let roleId = sessionConfig.roleId;
        if (!roleId) {
            const session = sessions.find(s => s.id === sessionId);
            roleId = session?.role_id || 'aws_architect';
        }
        console.log('Selected role ID:', roleId);

        const role = availableRoles.find(r => r.id === roleId);
        if (role) {
            currentRole = role;
            updateCurrentRoleDisplay();

            // 直接从会话配置恢复提示词，不需要请求服务器
            if (sessionConfig.customPrompt) {
                sessionPrompt = sessionConfig.customPrompt;
                systemPromptEditor.value = sessionConfig.customPrompt;
                console.log('Restored custom prompt for session:', sessionConfig.customPrompt.substring(0, 50) + '...');
            } else {
                sessionPrompt = '';
                // 从缓存获取角色默认提示词，如果没有缓存则请求服务器
                const roleDefaultPrompt = await getRoleDefaultPrompt(roleId);
                if (roleDefaultPrompt) {
                    originalPrompt = roleDefaultPrompt;
                    systemPromptEditor.value = roleDefaultPrompt;
                    console.log('Using cached role default prompt');
                } else {
                    console.log('No cached prompt found, this should not happen');
                }
            }
            console.log('Final prompt editor value:', systemPromptEditor.value.substring(0, 50) + '...');

            // 从会话配置恢复MCP选择
            if (sessionConfig.selectedMcps !== undefined) {
                // 如果会话配置中有MCP设置（包括空数组），使用它
                selectedMcps = [...sessionConfig.selectedMcps];
            } else {
                // 如果会话配置中没有MCP设置，使用角色默认配置
                resetMcpSelectionToDefault();
            }

            renderRoleList();
            renderMcpSelection();
        } else {
            // 如果角色不存在，使用默认角色
            const defaultRole = availableRoles.find(r => r.id === 'aws_architect') || availableRoles[0];
            if (defaultRole) {
                currentRole = defaultRole;
                updateCurrentRoleDisplay();

                // 获取并缓存默认角色的提示词
                const defaultPrompt = await getRoleDefaultPrompt(defaultRole.id);
                if (defaultPrompt) {
                    originalPrompt = defaultPrompt;
                    systemPromptEditor.value = defaultPrompt;
                }

                resetMcpSelectionToDefault();
                renderRoleList();
                renderMcpSelection();

                // 保存默认配置到会话
                saveCurrentSessionConfig();
            }
        }
    }
    
    // 删除会话
    function deleteSession(sessionId) {
        if (!confirm(`确定要删除此会话吗？此操作无法撤销。`)) {
            return;
        }

        // 从会话列表中删除
        sessions = sessions.filter(session => session.id !== sessionId);

        // 从会话历史中删除
        if (chatHistory[sessionId]) {
            delete chatHistory[sessionId];
        }

        // 删除会话配置
        deleteSessionConfig(sessionId);

        // 保存更新到 localStorage
        saveSessionsToLocalStorage();

        // 如果删除的是当前会话，创建一个新的
        if (sessionId === currentSessionId) {
            // 如果还有其他会话，选择第一个
            if (sessions.length > 0) {
                selectSession(sessions[0].id);
            } else {
                // 否则创建新的
                currentSessionId = null;
                localStorage.removeItem('currentSessionId');
                createSession();
            }
        } else {
            // 仅更新会话列表
            renderSessions();
        }
    }

    // 清空所有会话
    function clearAllSessions() {
        if (!confirm(`确定要删除所有会话吗？此操作无法撤销。`)) {
            return;
        }

        // 清空会话列表和历史记录
        sessions = [];
        chatHistory = {};
        currentSessionId = null;

        // 清除 localStorage
        localStorage.removeItem('sessions');
        localStorage.removeItem('chatHistory');
        localStorage.removeItem('currentSessionId');
        localStorage.removeItem('sessionConfigs');  // 清除所有会话配置

        // 创建一个新的会话
        createSession();

        // 更新会话列表显示
        renderSessions();
    }
    
    // 发送消息
    function sendMessage() {
        const message = userInput.value.trim();
        if (message === '' && !currentImageData) return;

        // 如果是会话的第一个问题，更新会话标题
        updateSessionTitleFromFirstMessage(message);

        addUserMessage(message);
        
        // 如果有图片，在用户消息下添加图片预览
        if (currentImageData) {
            const imageDiv = document.createElement('div');
            imageDiv.className = 'message user-message';
            imageDiv.innerHTML = `
                <div class="message-content">
                    <img src="${currentImageData}" alt="用户上传图片" style="max-width: 200px; max-height: 150px;">
                </div>
            `;
            chatMessages.appendChild(imageDiv);

            // 为新添加的图片添加点击事件
            addImageClickHandlers(imageDiv);
        }
        
        userInput.value = '';
        
        // 保存该消息到会话历史
        if (currentSessionId) {
            saveChatToHistory();
        }

        // Create a streaming response container
        const streamingMsgId = 'streaming-response-' + Date.now();
        const responseDiv = addBotMessage('<div class="streaming-status">思考中...</div>', streamingMsgId);
        const streamingContent = responseDiv.querySelector('.markdown-content');

        // Track the accumulated response content
        let accumulatedContent = '';

        // Use fetch with streaming to get the response
        // 创建支持超时的fetch请求
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 180000); // 设置3分钟超时
        
        // Get token from URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('token');
        
        if (!token) {
            streamingContent.innerHTML = `<div class="error">认证错误: 缺少访问令牌。请在URL中提供有效的token参数。</div>`;
            return;
        }
        
        // 获取当前的自定义提示词
        const currentPrompt = systemPromptEditor.value.trim();
        const isCustomPrompt = currentPrompt !== originalPrompt;

        // 保存当前会话的配置到本地存储
        if (currentSessionId) {
            const sessionConfig = {
                roleId: currentRole ? currentRole.id : null,
                customPrompt: isCustomPrompt ? currentPrompt : null,
                selectedMcps: [...selectedMcps]
            };
            saveSessionConfig(currentSessionId, sessionConfig);
        }

        // 创建请求体
        const requestBody = {
            message: message,
            session_id: currentSessionId,
            role_id: currentRole ? currentRole.id : 'aws_architect',
            custom_prompt: isCustomPrompt ? currentPrompt : null,  // 只有修改了才发送自定义提示词
            enabled_mcps: selectedMcps  // 发送用户选择的MCP列表，空数组表示不使用任何MCP
        };
        
        // 如果有图片，添加到请求体中
        if (currentImageData) {
            requestBody.image = {
                data: currentImageData.split(',')[1], // 去掉 data URL 前缀
                format: currentImageType.split('/')[1] // 从 image/png 或 image/jpeg 中提取格式
            };
            
            // 清除当前图片数据
            clearImagePreview();
        }
        
        const bodyCnt = JSON.stringify(requestBody);
        sha256(bodyCnt).then(hash => {
            fetch(`/api/chat_stream?token=${token}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-amz-content-sha256': hash,
                },
                body: bodyCnt,
                signal: controller.signal
            })
                .then(response => {
                    const reader = response.body.getReader();
                    const decoder = new TextDecoder();

                    function readStream() {
                        return reader.read().then(({ done, value }) => {
                            if (done) {
                                return;
                            }

                            const chunk = decoder.decode(value);
                            const lines = chunk.split('\n\n');

                            for (const line of lines) {
                                if (line.startsWith('data: ')) {
                                    try {
                                        const data = JSON.parse(line.substring(6));
                                        // Accumulate response content
                                        if (data.type === 'response') {
                                            accumulatedContent += data.content;
                                        }

                                        processStreamingData(data, streamingContent, accumulatedContent);
                                        
                                        // 处理会话创建
                                        if (data.type === 'session_created') {
                                            const sessionId = data.session_id;
                                            
                                            // 如果是新会话，添加到列表中
                                            if (!sessions.some(s => s.id === sessionId)) {
                                                const newSession = {
                                                    id: sessionId,
                                                    title: '新会话',  // 初始标题，等待第一个问题后更新
                                                    created_at: new Date().toISOString()
                                                };
                                                sessions.push(newSession);
                                            }
                                            
                                            // 初始化会话历史
                                            if (!chatHistory[sessionId]) {
                                                chatHistory[sessionId] = [];
                                            }
                                            
                                            currentSessionId = sessionId;
                                            localStorage.setItem('currentSessionId', currentSessionId);
                                            console.log('New session created:', currentSessionId);
                                            
                                            // 保存到本地存储
                                            saveSessionsToLocalStorage();
                                        }
                                        
                                        // 收到完整响应后保存到会话历史
                                        if (data.type === 'complete' && currentSessionId) {
                                            saveChatToHistory();
                                        }
                                    } catch (e) {
                                        console.error('Error parsing streaming data:', e, line.substring(6));
                                    }
                                }
                            }

                            return readStream();
                        });
                    }

                    clearTimeout(timeoutId); // 清除超时计时器
                    return readStream();
                })
                .catch(error => {
                    clearTimeout(timeoutId); // 清除超时计时器
                    const errorMessage = error.name === 'AbortError' 
                        ? '抱歉，请求超时。服务器响应时间过长，请稍后再试。' 
                        : '抱歉，连接服务器时出现了错误。请检查您的网络连接。';
                    streamingContent.innerHTML = `<div class="error">${errorMessage}</div>`;
                    console.error('Error:', error);
                });
        });
    }

    // 处理流式数据
    function processStreamingData(data, contentElement, accumulatedContent) {
        switch (data.type) {
            case 'connected':
                contentElement.innerHTML = `<div class="streaming-status">${data.message}</div>`;
                break;

            case 'step':
            case 'progress':
                const progressBar = `<div class="progress-bar" style="height: 4px; background-color: #007bff; width: ${data.progress}%; margin: 5px 0;"></div>`;
                contentElement.innerHTML = `<div class="streaming-status">${data.message}</div>${progressBar}`;
                break;

            case 'status':
                // 处理状态更新事件 - 简化显示
                let statusContainer = contentElement.querySelector('.status-container');

                if (!statusContainer) {
                    statusContainer = document.createElement('div');
                    statusContainer.className = 'status-container';
                    statusContainer.style.cssText = `
                        font-size: 0.85em;
                        color: #999;
                        margin-bottom: 5px;
                        padding: 3px 6px;
                        background-color: #f1f3f4;
                        border-radius: 12px;
                        display: inline-block;
                    `;
                    contentElement.appendChild(statusContainer);
                }

                // 更新状态信息
                statusContainer.textContent = data.content;
                break;

            case 'heartbeat':
                // 心跳事件，不显示任何内容，只用于保持连接
                break;

            case 'partial':
                // Handle streaming deltas
                // Check if we already have a streaming container
                let streamContainer = contentElement.querySelector('.streaming-container');

                if (!streamContainer) {
                    // First partial response, create container
                    streamContainer = document.createElement('div');
                    streamContainer.className = 'streaming-container';
                    contentElement.appendChild(streamContainer);
                }

                // Append the new content
                streamContainer.innerHTML += data.content;
                break;

            case 'response':
                // Show the accumulated response with markdown parsing
                const processedContent = processAnswerTags(accumulatedContent);

                // 查找或创建响应容器
                let responseContainer = contentElement.querySelector('.response-container');
                if (!responseContainer) {
                    responseContainer = document.createElement('div');
                    responseContainer.className = 'response-container';
                    contentElement.appendChild(responseContainer);
                }

                responseContainer.innerHTML = marked.parse(processedContent);

                // 为所有 answer 块和代码块添加复制功能
                addCopyFunctionalityToAnswerBlocks(contentElement.closest('.message'));
                addCopyFunctionalityToCodeBlocks(contentElement.closest('.message'));
                // 为图片添加点击事件
                addImageClickHandlers(contentElement.closest('.message'));
                break;

            case 'delta':
                // 处理文本增量更新
                let deltaContainer = contentElement.querySelector('.delta-container');
                if (!deltaContainer) {
                    deltaContainer = document.createElement('div');
                    deltaContainer.className = 'delta-container';
                    contentElement.appendChild(deltaContainer);
                }
                deltaContainer.innerHTML += data.content || '';
                break;

            case 'complete':
                // Response is fully complete - 清理状态信息，只保留最终响应
                const completeStatusContainer = contentElement.querySelector('.status-container');
                if (completeStatusContainer) {
                    completeStatusContainer.style.display = 'none'; // 隐藏状态信息
                }

                // Convert any remaining streaming content to proper markdown
                const completeStreamingContainer = contentElement.querySelector('.streaming-container');
                const completeDeltaContainer = contentElement.querySelector('.delta-container');
                const completeResponseContainer = contentElement.querySelector('.response-container');

                if (completeStreamingContainer || completeDeltaContainer || completeResponseContainer) {
                    let finalContent = accumulatedContent;

                    if (completeStreamingContainer) {
                        finalContent = completeStreamingContainer.innerHTML;
                    } else if (completeDeltaContainer) {
                        finalContent = completeDeltaContainer.innerHTML;
                    }

                    const processedStreamContent = processAnswerTags(finalContent);
                    contentElement.innerHTML = marked.parse(processedStreamContent);

                    // 为所有 answer 块和代码块添加复制功能
                    addCopyFunctionalityToAnswerBlocks(contentElement.closest('.message'));
                    addCopyFunctionalityToCodeBlocks(contentElement.closest('.message'));
                    // 为图片添加点击事件
                    addImageClickHandlers(contentElement.closest('.message'));
                }
                break;

            case 'error':
                contentElement.innerHTML = `<div class="error">错误: ${data.error}</div>`;
                break;
        }

        scrollToBottom();
    }

    // 统一的事件处理函数
    function handleMessageCopy(e) {
        e.preventDefault();
        e.stopPropagation();
        const messageText = this.dataset.message;

        // 解码HTML实体并清理空格换行
        const decodedText = messageText
            .replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&')
            .replace(/\s+/g, ' ')
            .trim();

        copyToClipboard(decodedText);
    }

    function handleAnswerCopy(e) {
        e.preventDefault();
        e.stopPropagation();
        const answerId = this.dataset.answerId;
        const container = this.closest('.message');
        const answerBlock = container.querySelector(`[data-answer-id="${answerId}"]`);

        if (answerBlock) {
            const textContent = getAnswerTextContent(answerBlock);
            copyToClipboard(textContent, this, false);
        }
    }

    function handleCodeCopy(e) {
        e.preventDefault();
        e.stopPropagation();
        const codeId = this.getAttribute('data-code-id');
        const container = this.closest('.message');
        const targetPre = container.querySelector(`pre[data-code-id="${codeId}"]`);

        if (targetPre) {
            const codeText = getCodeTextContent(targetPre);
            copyToClipboard(codeText, this, false);
        }
    }

    // 降级复制方案
    function fallbackCopyTextToClipboard(text) {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.cssText = "position:fixed;top:0;left:0;opacity:0;";

        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();

        try {
            const successful = document.execCommand('copy');
            document.body.removeChild(textArea);
            return successful;
        } catch (err) {
            console.error('降级方案复制出错:', err);
            document.body.removeChild(textArea);
            return false;
        }
    }

    // 根据第一个消息更新会话标题
    function updateSessionTitleFromFirstMessage(message) {
        if (!currentSessionId || !message.trim()) return;

        // 查找当前会话
        const currentSession = sessions.find(s => s.id === currentSessionId);
        if (!currentSession) return;

        // 如果当前标题是默认的"新会话"，则使用第一个问题更新
        if (currentSession.title === '新会话') {
            // 创建缩略标题
            const truncatedTitle = truncateText(message, 30);
            currentSession.title = truncatedTitle;

            // 保存到本地存储
            saveSessionsToLocalStorage();

            // 如果会话管理模态框正在显示，更新显示
            if (document.getElementById('sessionModal').classList.contains('show')) {
                renderSessions();
            }
        }
    }

    // 截断文本并添加省略号
    function truncateText(text, maxLength) {
        if (text.length <= maxLength) {
            return text;
        }

        // 在适当的位置截断，避免在单词中间截断
        let truncated = text.substring(0, maxLength);

        // 如果截断点不是空格，尝试找到最近的空格
        if (text[maxLength] && text[maxLength] !== ' ') {
            const lastSpaceIndex = truncated.lastIndexOf(' ');
            if (lastSpaceIndex > maxLength * 0.7) { // 只有当空格位置不太靠前时才使用
                truncated = truncated.substring(0, lastSpaceIndex);
            }
        }

        return truncated + '...';
    }

    // 显示复制通知
    function showCopyNotification(message, isSuccess = true) {
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = 'copy-notification';
        notification.textContent = message;

        const backgroundColor = isSuccess ? '#28a745' : '#dc3545';
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${backgroundColor};
            color: white;
            padding: 8px 16px;
            border-radius: 4px;
            font-size: 14px;
            z-index: 9999;
            opacity: 0;
            transition: opacity 0.3s;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        `;

        document.body.appendChild(notification);

        // 显示动画
        setTimeout(() => {
            notification.style.opacity = '1';
        }, 10);

        // 2秒后移除
        setTimeout(() => {
            notification.style.opacity = '0';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 2000);
    }

    // 简化的图片查看功能
    let isZoomed = false;

    // 图片点击放大功能 - 简化版本
    function showImageModal(imageSrc, imageAlt = '预览图片') {
        const modalImage = document.getElementById('modalImage');
        const modalTitle = document.getElementById('imageModalLabel');
        const imageContainer = modalImage.parentElement;

        modalImage.src = imageSrc;
        modalImage.alt = imageAlt;

        // 优化标题显示，移除冗余文本
        let displayTitle = imageAlt;
        if (imageAlt === '用户上传图片' || imageAlt === '预览图片') {
            displayTitle = '图片预览';
        }
        modalTitle.textContent = displayTitle;

        // 重置状态
        resetImageState(modalImage, imageContainer);

        // 添加简单的点击交互
        setupSimpleImageInteraction(modalImage, imageContainer);

        imageModal.show();
    }

    // 重置图片状态
    function resetImageState(image, container) {
        isZoomed = false;
        image.classList.remove('zoomed');
        container.classList.remove('zoomed');
        image.style.transform = 'scale(1)';
    }

    // 设置简单的图片交互
    function setupSimpleImageInteraction(image, container) {
        // 清除之前的事件监听器
        image.onclick = null;

        // 点击切换放大/原始大小
        image.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            toggleSimpleZoom(image, container);
        });
    }

    // 简单的缩放切换
    function toggleSimpleZoom(image, container) {
        if (!isZoomed) {
            // 放大到2倍
            isZoomed = true;
            image.classList.add('zoomed');
            container.classList.add('zoomed');
            image.style.transform = 'scale(2)';
        } else {
            // 恢复原始大小
            resetImageState(image, container);
        }
    }

    // 为图片添加点击事件
    function addImageClickHandlers(container) {
        const images = container.querySelectorAll('img');
        images.forEach(img => {
            // 为了确保事件监听器被正确添加，我们总是重新添加
            if (img.hasAttribute('data-clickable')) {
                // 移除旧属性，重新添加
                img.removeAttribute('data-clickable');
            }

            img.setAttribute('data-clickable', 'true');
            img.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                showImageModal(this.src, this.alt || '预览图片');
            });
        });
    }

    // 为整个聊天区域的现有图片添加点击事件
    function addClickHandlersToExistingImages() {
        // 为所有现有图片添加点击事件，无论是否已经添加过
        const allImages = chatMessages.querySelectorAll('img');
        allImages.forEach(img => {
            // 移除旧的标记，重新添加事件
            img.removeAttribute('data-clickable');
            img.setAttribute('data-clickable', 'true');

            // 移除可能存在的旧事件监听器（通过克隆节点）
            const newImg = img.cloneNode(true);
            img.parentNode.replaceChild(newImg, img);

            // 为新节点添加事件监听器
            newImg.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                showImageModal(this.src, this.alt || '预览图片');
            });
        });
    }

    // 清除图片预览
    function clearImagePreview() {
        currentImageData = null;
        currentImageType = null;
        imagePreview.src = '';
        imagePreviewContainer.classList.add('d-none');
        imageUploadInput.value = '';
    }

    // 图片压缩函数
    function compressAndProcessImage(file) {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        const img = new Image();

        img.onload = function() {
            // 计算压缩后的尺寸
            let { width, height } = calculateCompressedSize(img.width, img.height);

            // 设置canvas尺寸
            canvas.width = width;
            canvas.height = height;

            // 绘制压缩后的图片
            ctx.drawImage(img, 0, 0, width, height);

            // 根据原始格式选择输出格式和质量
            let outputFormat = 'image/jpeg';
            let quality = 0.8;

            // PNG图片通常压缩效果更好转为JPEG
            if (file.type === 'image/png' && file.size > 2 * 1024 * 1024) {
                outputFormat = 'image/jpeg';
                quality = 0.75;
            } else if (file.type === 'image/jpeg') {
                outputFormat = 'image/jpeg';
                quality = file.size > 5 * 1024 * 1024 ? 0.7 : 0.8;
            } else {
                // 小的PNG文件保持原格式
                outputFormat = file.type;
                quality = 0.9;
            }

            // 转换为DataURL
            const compressedDataUrl = canvas.toDataURL(outputFormat, quality);

            // 检查压缩后的大小
            const compressedSize = Math.round((compressedDataUrl.length - 'data:image/jpeg;base64,'.length) * 3/4);

            // 如果仍然太大，进一步压缩
            if (compressedSize > 8 * 1024 * 1024) {
                const furtherCompressed = canvas.toDataURL('image/jpeg', 0.5);
                const finalSize = Math.round((furtherCompressed.length - 'data:image/jpeg;base64,'.length) * 3/4);

                if (finalSize > 10 * 1024 * 1024) {
                    alert('图片压缩后仍然过大，请选择更小的图片');
                    return;
                }

                // 使用进一步压缩的版本
                currentImageData = furtherCompressed;
                currentImageType = 'image/jpeg';
            } else {
                currentImageData = compressedDataUrl;
                currentImageType = outputFormat;
            }

            // 显示图片预览
            imagePreview.src = currentImageData;
            imagePreviewContainer.classList.remove('d-none');

            // 显示压缩信息
            const originalSize = (file.size / 1024 / 1024).toFixed(2);
            const compressedSizeMB = (compressedSize / 1024 / 1024).toFixed(2);
            console.log(`图片压缩完成: ${originalSize}MB → ${compressedSizeMB}MB`);
        };

        img.onerror = function() {
            alert('图片加载失败，请选择有效的图片文件');
        };

        // 创建图片URL
        img.src = URL.createObjectURL(file);
    }

    // 计算压缩后的尺寸
    function calculateCompressedSize(originalWidth, originalHeight) {
        const maxWidth = 1920;
        const maxHeight = 1080;
        const maxPixels = 1920 * 1080; // 约2MP

        let width = originalWidth;
        let height = originalHeight;

        // 如果像素总数超过限制，按比例缩小
        const totalPixels = width * height;
        if (totalPixels > maxPixels) {
            const ratio = Math.sqrt(maxPixels / totalPixels);
            width = Math.round(width * ratio);
            height = Math.round(height * ratio);
        }

        // 确保不超过最大尺寸
        if (width > maxWidth) {
            height = Math.round(height * (maxWidth / width));
            width = maxWidth;
        }

        if (height > maxHeight) {
            width = Math.round(width * (maxHeight / height));
            height = maxHeight;
        }

        return { width, height };
    }

    // 图片上传相关功能
    imageUploadBtn.addEventListener('click', function() {
        imageUploadInput.click();
    });
    
    imageUploadInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (!file) return;

        // 验证文件类型
        if (!['image/jpeg', 'image/png'].includes(file.type)) {
            alert('只支持 JPEG 和 PNG 格式的图片');
            return;
        }

        // 验证文件大小，限制为 20MB（压缩前）
        if (file.size > 20 * 1024 * 1024) {
            alert('图片大小不能超过 20MB');
            return;
        }

        // 压缩并处理图片
        compressAndProcessImage(file);
    });
    
    removeImageBtn.addEventListener('click', clearImagePreview);

    // 事件监听
    sendButton.addEventListener('click', sendMessage);

    userInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // 会话管理事件
    sessionManagerBtn.addEventListener('click', function() {
        sessionModal.show();
        renderSessions(); // 显示会话列表
    });
    
    createSessionBtn.addEventListener('click', createSession);
    
    clearAllSessionsBtn.addEventListener('click', function() {
        // 清空所有会话
        clearAllSessions();
    });

    // 角色相关事件监听
    roleSelectBtn.addEventListener('click', function() {
        roleModal.show();
        // 不重新加载提示词，保持用户当前的编辑内容
    });

    // 提示词编辑时实时保存
    systemPromptEditor.addEventListener('input', function() {
        // 延迟保存，避免频繁保存
        clearTimeout(systemPromptEditor._saveTimeout);
        systemPromptEditor._saveTimeout = setTimeout(() => {
            saveCurrentSessionConfig();
        }, 500);
    });

    // 重置按钮功能
    resetPromptBtn.addEventListener('click', function() {
        systemPromptEditor.value = originalPrompt;
        sessionPrompt = '';  // 清除会话级别的自定义提示词
        saveCurrentSessionConfig();  // 保存重置状态
        showCopyNotification('已重置到角色默认提示词', true);
    });

    // 处理移动端键盘弹出时的视口问题
    function handleViewportResize() {
        if (window.innerWidth <= 768) {
            const vh = window.innerHeight * 0.01;
            document.documentElement.style.setProperty('--vh', `${vh}px`);

            // 处理iOS Safari地址栏隐藏/显示
            const chatContainer = document.querySelector('.chat-container');
            if (chatContainer) {
                chatContainer.style.height = `${window.innerHeight}px`;
            }
        }
    }

    // 监听窗口大小变化（键盘弹出/收起）
    window.addEventListener('resize', handleViewportResize);
    window.addEventListener('orientationchange', () => {
        setTimeout(handleViewportResize, 100);
    });

    // 初始化视口
    handleViewportResize();

    // 输入框聚焦时的处理
    userInput.addEventListener('focus', function() {
        // 短暂延迟后滚动到输入框
        setTimeout(() => {
            this.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 300);
    });

    // 为代码块添加复制功能
    function addCopyFunctionalityToCodeBlocks(container) {
        const preElements = container.querySelectorAll('pre');
        preElements.forEach((pre, index) => {
            // 避免重复添加按钮
            if (pre.querySelector('.copy-code-btn')) {
                return;
            }

            // 为代码块添加唯一ID
            const codeId = `code-${Date.now()}-${index}`;
            pre.setAttribute('data-code-id', codeId);

            // 创建复制按钮
            const copyButton = document.createElement('button');
            copyButton.className = 'copy-code-btn';
            copyButton.setAttribute('data-code-id', codeId);
            copyButton.title = '复制代码';
            copyButton.innerHTML = `
                <svg viewBox="0 0 16 16" fill="currentColor">
                    <path d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1v-1z"/>
                    <path d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5h3zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3z"/>
                </svg>
            `;

            // 添加按钮到代码块
            pre.style.position = 'relative';
            pre.appendChild(copyButton);

            // 添加点击事件
            copyButton.addEventListener('click', handleCodeCopy);
        });
    }

    // 获取代码块的纯文本内容
    function getCodeTextContent(preElement) {
        // 创建临时克隆
        const clone = preElement.cloneNode(true);

        // 移除复制按钮
        const copyBtn = clone.querySelector('.copy-code-btn');
        if (copyBtn) {
            copyBtn.remove();
        }

        // 获取文本内容
        return clone.textContent || clone.innerText || '';
    }



    // 键盘事件监听 - ESC键关闭图片模态框
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            // 如果图片模态框是打开的，关闭它
            const imageModalElement = document.getElementById('imageModal');
            if (imageModalElement.classList.contains('show')) {
                imageModal.hide();
            }
        }
    });

    // 初始化时为现有图片添加点击事件
    addClickHandlersToExistingImages();

    // 初始化聊天界面
    if (window.innerWidth > 768) {
        userInput.focus();
    }
});
