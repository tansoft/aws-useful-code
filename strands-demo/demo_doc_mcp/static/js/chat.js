document.addEventListener('DOMContentLoaded', function () {
    const chatMessages = document.getElementById('chatMessages');
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');
    const sessionManagerBtn = document.getElementById('sessionManagerBtn');
    const createSessionBtn = document.getElementById('createSessionBtn');
    const clearAllSessionsBtn = document.getElementById('clearAllSessionsBtn');
    const sessionsContainer = document.getElementById('sessionsContainer');
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

    const sessionModal = new bootstrap.Modal(document.getElementById('sessionModal'));
    
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
    
    loadSessionsFromLocalStorage();
    function addUserMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        messageDiv.innerHTML = `
            <div class="message-content">
                ${text}
                <button class="copy-message-btn" title="复制并重新输入" data-message="${text.replace(/"/g, '&quot;')}">
                    ⧉
                </button>
            </div>
        `;
        chatMessages.appendChild(messageDiv);
        scrollToBottom();

        const copyBtn = messageDiv.querySelector('.copy-message-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                copyUserMessage(this.dataset.message);
            });
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
                    复制
                </button>
            </div>`;
        });
    }

    // 为 answer 块添加复制功能
    function addCopyFunctionalityToAnswerBlocks(container) {
        const copyButtons = container.querySelectorAll('.copy-answer-btn');
        copyButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();

                const answerId = this.dataset.answerId;
                const answerBlock = container.querySelector(`[data-answer-id="${answerId}"]`);

                if (answerBlock) {
                    // 获取纯文本内容，排除复制按钮的文本
                    const textContent = getAnswerTextContent(answerBlock);
                    copyAnswerToClipboard(textContent, this);
                }
            });
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

    // 复制 answer 内容到剪贴板
    function copyAnswerToClipboard(text, buttonElement) {
        const cleanText = text.trim();

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(cleanText).then(() => {
                showCopyFeedback(buttonElement, '已复制!', true);
            }).catch(err => {
                console.error('复制失败:', err);
                fallbackCopyTextToClipboard(cleanText);
                showCopyFeedback(buttonElement, '已复制!', true);
            });
        } else {
            // 降级方案
            const success = fallbackCopyTextToClipboard(cleanText);
            showCopyFeedback(buttonElement, success ? '已复制!' : '复制失败', success);
        }
    }

    // 显示复制反馈
    function showCopyFeedback(buttonElement, message, isSuccess) {
        const originalText = buttonElement.innerHTML;
        const originalColor = buttonElement.style.color;

        // 更新按钮文本和颜色
        buttonElement.innerHTML = `
            <svg viewBox="0 0 16 16" fill="currentColor">
                <path d="M13.854 3.646a.5.5 0 0 1 0 .708l-7 7a.5.5 0 0 1-.708 0l-3.5-3.5a.5.5 0 1 1 .708-.708L6.5 10.293l6.646-6.647a.5.5 0 0 1 .708 0z"/>
            </svg>
            ${message}
        `;
        buttonElement.style.color = isSuccess ? '#28a745' : '#dc3545';

        // 2秒后恢复原状
        setTimeout(() => {
            buttonElement.innerHTML = originalText;
            buttonElement.style.color = originalColor;
        }, 2000);

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
            addBotMessage('<p>你好，我是AWS解决方案架构师！👋 </p><p>你可以问我任何AWS的问题。例如：EC2的带宽是多少？</p>');
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
                            ⧉
                        </button>
                    </div>
                `;
                chatMessages.appendChild(messageDiv);

                // 为历史消息的复制按钮添加事件监听器
                const copyBtn = messageDiv.querySelector('.copy-message-btn');
                if (copyBtn) {
                    copyBtn.addEventListener('click', function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        console.log('历史消息复制按钮被点击了'); // 调试日志
                        console.log('要复制的内容:', plainTextContent); // 调试日志
                        copyUserMessage(plainTextContent);
                    });
                }
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

                // 为历史消息中的 answer 块添加复制功能
                addCopyFunctionalityToAnswerBlocks(messageDiv);
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
    
    // 创建一个新会话
    function createSession() {
        // 生成新的会话 ID
        const sessionId = generateUUID();
        const newSession = {
            id: sessionId,
            title: '新会话',  // 初始标题，等待第一个问题后更新
            created_at: new Date().toISOString()
        };
        
        // 添加到会话列表
        sessions.push(newSession);
        
        // 初始化会话历史
        chatHistory[sessionId] = [];
        
        // 保存到 localStorage
        saveSessionsToLocalStorage();
        
        // 设置为当前会话
        currentSessionId = sessionId;
        localStorage.setItem('currentSessionId', sessionId);
        
        // 清空聊天消息
        chatMessages.innerHTML = '';
        addBotMessage('<p>你好，我是AWS解决方案架构师！👋 </p><p>你可以问我任何AWS的问题。例如：EC2的带宽是多少？</p>');
        
        // 将初始消息保存到会话历史
        saveChatToHistory();
        
        // 关闭模态框
        sessionModal.hide();
        
        // 更新会话列表
        renderSessions();
    }
    
    // 选择会话
    function selectSession(sessionId) {
        // 如果是当前会话，则不做切换
        if (sessionId === currentSessionId) {
            sessionModal.hide();
            return;
        }
        
        // 保存当前会话的聊天历史
        if (currentSessionId) {
            saveChatToHistory();
        }
        
        // 更新当前会话 ID
        currentSessionId = sessionId;
        localStorage.setItem('currentSessionId', sessionId);
        
        // 加载选中会话的聊天记录
        loadSessionChat(sessionId);
        
        // 关闭模态框
        sessionModal.hide();
        
        // 更新会话列表（高亮当前选中项）
        renderSessions();
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
        
        // 创建请求体
        const requestBody = { 
            message: message,
            session_id: currentSessionId
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
        
        fetch(`./api/chat_stream?token=${token}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody),
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

                // 为所有 answer 块添加复制功能
                addCopyFunctionalityToAnswerBlocks(contentElement.closest('.message'));
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

                    // 为所有 answer 块添加复制功能
                    addCopyFunctionalityToAnswerBlocks(contentElement.closest('.message'));
                }
                break;

            case 'error':
                contentElement.innerHTML = `<div class="error">错误: ${data.error}</div>`;
                break;
        }

        scrollToBottom();
    }

    // 复制用户消息功能
    function copyUserMessage(messageText) {
        console.log('开始复制:', messageText); // 调试日志

        // 解码HTML实体并清理空格换行
        let decodedText = messageText.replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');

        // 清理多余的空格和换行
        decodedText = decodedText
            .replace(/\s+/g, ' ')  // 将多个空格/换行/制表符替换为单个空格
            .trim();               // 去除首尾空格

        console.log('清理后的文本:', decodedText); // 调试日志

        // 复制到剪贴板
        if (navigator.clipboard && navigator.clipboard.writeText) {
            console.log('使用 navigator.clipboard API'); // 调试日志
            navigator.clipboard.writeText(decodedText).then(() => {
                console.log('复制成功'); // 调试日志
                showCopyNotification('已复制到剪贴板');
            }).catch(err => {
                console.error('复制失败:', err);
                // 尝试降级方案
                fallbackCopyTextToClipboard(decodedText);
            });
        } else {
            console.log('使用降级方案'); // 调试日志
            // 降级方案
            fallbackCopyTextToClipboard(decodedText);
        }
    }

    // 降级复制方案
    function fallbackCopyTextToClipboard(text) {
        const textArea = document.createElement("textarea");
        textArea.value = text;

        // 避免在iOS上出现缩放
        textArea.style.top = "0";
        textArea.style.left = "0";
        textArea.style.position = "fixed";
        textArea.style.opacity = "0";

        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();

        let successful = false;
        try {
            successful = document.execCommand('copy');
            if (successful) {
                console.log('降级方案复制成功'); // 调试日志
                showCopyNotification('已复制到剪贴板');
            } else {
                console.log('降级方案复制失败'); // 调试日志
                showCopyNotification('复制失败', false);
            }
        } catch (err) {
            console.error('降级方案复制出错:', err);
            showCopyNotification('复制失败', false);
        }

        document.body.removeChild(textArea);
        return successful;
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

    // 清除图片预览
    function clearImagePreview() {
        currentImageData = null;
        currentImageType = null;
        imagePreview.src = '';
        imagePreviewContainer.classList.add('d-none');
        imageUploadInput.value = '';
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
        
        // 验证文件大小，限制为 8MB
        if (file.size > 8 * 1024 * 1024) {
            alert('图片大小不能超过 8MB');
            return;
        }
        
        // 读取文件为 DataURL
        const reader = new FileReader();
        reader.onload = function(e) {
            // 存储图片数据和类型
            currentImageData = e.target.result;
            currentImageType = file.type;
            
            // 显示图片预览
            imagePreview.src = currentImageData;
            imagePreviewContainer.classList.remove('d-none');
        };
        reader.readAsDataURL(file);
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

    // 初始化聊天界面
    if (window.innerWidth > 768) {
        userInput.focus();
    }
});