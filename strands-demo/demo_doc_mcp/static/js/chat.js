// 聊天应用主要JavaScript文件

document.addEventListener('DOMContentLoaded', function () {
    const chatMessages = document.getElementById('chatMessages');
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');
    const sessionManagerBtn = document.getElementById('sessionManagerBtn');
    const createSessionBtn = document.getElementById('createSessionBtn');
    const refreshSessionsBtn = document.getElementById('refreshSessionsBtn');
    const sessionsContainer = document.getElementById('sessionsContainer');
    const imageUploadBtn = document.getElementById('imageUploadBtn');
    const imageUploadInput = document.getElementById('imageUploadInput');
    const imagePreviewContainer = document.getElementById('imagePreviewContainer');
    const imagePreview = document.getElementById('imagePreview');
    const removeImageBtn = document.getElementById('removeImageBtn');
    
    // 全局变量，用于存储当前上传的图片数据
    let currentImageData = null;
    let currentImageType = null;
    
    // Session management
    let currentSessionId = localStorage.getItem('currentSessionId') || null;
    let sessions = [];
    let chatHistory = {}; // 存储各个会话的对话历史
    
    // 初始化会话模态框
    const sessionModal = new bootstrap.Modal(document.getElementById('sessionModal'));
    
    // 从 localStorage 加载会话数据
    function loadSessionsFromLocalStorage() {
        try {
            // 加载会话列表
            const savedSessions = localStorage.getItem('sessions');
            if (savedSessions) {
                sessions = JSON.parse(savedSessions);
            }
            
            // 加载各个会话的聊天历史
            const savedChatHistory = localStorage.getItem('chatHistory');
            if (savedChatHistory) {
                chatHistory = JSON.parse(savedChatHistory);
            }
            
            // 渲染会话列表
            renderSessions();
            
            // 如果有当前会话，加载其内容
            if (currentSessionId && chatHistory[currentSessionId]) {
                loadSessionChat(currentSessionId);
            }
        } catch (error) {
            console.error('Error loading sessions from localStorage:', error);
        }
    }
    
    // 保存会话数据到 localStorage
    function saveSessionsToLocalStorage() {
        try {
            localStorage.setItem('sessions', JSON.stringify(sessions));
            localStorage.setItem('chatHistory', JSON.stringify(chatHistory));
        } catch (error) {
            console.error('Error saving sessions to localStorage:', error);
        }
    }
    
    // 初始化加载会话
    loadSessionsFromLocalStorage();

    // 添加用户消息到聊天界面
    function addUserMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        messageDiv.innerHTML = `
            <div class="message-content">
                ${text}
            </div>
        `;
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    // 添加机器人消息到聊天界面
    function addBotMessage(text, id = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message';
        if (id) {
            messageDiv.id = id;
        }
        messageDiv.innerHTML = `
            <div class="message-content markdown-content">
                ${marked.parse(text)}
            </div>
        `;
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
        return messageDiv;
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
            const content = msg.querySelector('.message-content').innerHTML;
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
                messageDiv.innerHTML = `
                    <div class="message-content">
                        ${msg.content}
                    </div>
                `;
                chatMessages.appendChild(messageDiv);
            } else {
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message bot-message';
                messageDiv.innerHTML = `
                    <div class="message-content markdown-content">
                        ${msg.content}
                    </div>
                `;
                chatMessages.appendChild(messageDiv);
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
            title: `会话 ${new Date().toLocaleDateString()}`,
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
    
    // 发送消息
    function sendMessage() {
        const message = userInput.value.trim();
        if (message === '' && !currentImageData) return;

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

        // Track the response building process
        let finalResponse = '';
        let currentStep = '';

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
        
        fetch(`/api/chat_stream?token=${token}`, {
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
                                    processStreamingData(data, streamingContent);

                                    // Save final response if received
                                    if (data.type === 'response') {
                                        finalResponse = data.content;
                                    }
                                    
                                    // 处理会话创建
                                    if (data.type === 'session_created') {
                                        const sessionId = data.session_id;
                                        
                                        // 如果是新会话，添加到列表中
                                        if (!sessions.some(s => s.id === sessionId)) {
                                            const newSession = {
                                                id: sessionId,
                                                title: `会话 ${new Date().toLocaleDateString()}`,
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
    function processStreamingData(data, contentElement) {
        switch (data.type) {
            case 'connected':
                contentElement.innerHTML = `<div class="streaming-status">${data.message}</div>`;
                break;

            case 'step':
            case 'progress':
                const progressBar = `<div class="progress-bar" style="height: 4px; background-color: #007bff; width: ${data.progress}%; margin: 5px 0;"></div>`;
                contentElement.innerHTML = `<div class="streaming-status">${data.message}</div>${progressBar}`;
                break;

            case 'partial':
                // Handle streaming deltas
                // Check if we already have a streaming container
                let streamContainer = contentElement.querySelector('.streaming-container');

                if (!streamContainer) {
                    // First partial response, create container
                    streamContainer = document.createElement('div');
                    streamContainer.className = 'streaming-container';
                    contentElement.innerHTML = ''; // Clear any previous status/progress
                    contentElement.appendChild(streamContainer);
                }

                // Append the new content
                streamContainer.innerHTML += data.content;
                break;

            case 'response':
                // Show the response with markdown parsing
                // If it's a final response after partials, replace everything
                contentElement.innerHTML = marked.parse(data.content);
                break;

            case 'complete':
                // Response is fully complete
                // Convert any remaining streaming content to proper markdown
                const streamingContainer = contentElement.querySelector('.streaming-container');
                if (streamingContainer) {
                    contentElement.innerHTML = marked.parse(streamingContainer.innerHTML);
                }
                break;

            case 'error':
                contentElement.innerHTML = `<div class="error">错误: ${data.error}</div>`;
                break;
        }

        scrollToBottom();
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
    
    refreshSessionsBtn.addEventListener('click', function() {
        // 刷新会话列表
        renderSessions();
    });

    // 初始化聊天界面
    userInput.focus();
});