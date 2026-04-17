document.addEventListener('DOMContentLoaded', () => {
    const chatContainer = document.getElementById('chat-container');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const statusIndicator = document.querySelector('.status-indicator');

    let currentVIN = "VIN1001";
    
    // Auto resize textarea
    chatInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        if(this.value.trim() === '') {
            this.style.height = 'auto'; // reset
        }
    });

    // User Profile Switcher
    const userProfileBtn = document.getElementById('user-profile-btn');
    const currentUsername = document.getElementById('current-username');
    const vinDropdown = document.getElementById('vin-dropdown');
    const vinList = document.getElementById('vin-list');

    // Populate dropdown
    const availableVINs = ["VIN1001", "VIN1002", "VIN1003", "VIN1004", "VIN1005", "VIN1006", "VIN1007", "VIN1008", "VIN1009", "VIN1010"];
    
    if (vinList) {
        availableVINs.forEach(vin => {
            const li = document.createElement('li');
            li.textContent = vin;
            if (vin === currentVIN) li.classList.add('active');
            
            li.addEventListener('click', () => {
                // Switch logic
                currentVIN = vin;
                currentUsername.textContent = `${currentVIN} 车主`;
                
                // Update active states
                document.querySelectorAll('#vin-list li').forEach(el => el.classList.remove('active'));
                li.classList.add('active');
                
                // Update welcome msg
                const welcomeP = document.querySelectorAll('.assistant-message .glass-bubble p');
                welcomeP.forEach(p => {
                    if (p.innerHTML.includes('您可以尝试回复')) {
                        p.innerHTML = `请问今天有什么可以帮您的？您可以尝试回复："*我是${currentVIN}车主，帮我查一下我2月的运行报告并给出保养建议*"`;
                    }
                });
                statusIndicator.innerHTML = `● 已切至 ${currentVIN}`;
                
                // Close dropdown
                vinDropdown.style.display = 'none';
            });
            vinList.appendChild(li);
        });
    }

    if (userProfileBtn) {
        userProfileBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (vinDropdown.style.display === 'none' || vinDropdown.style.display === '') {
                vinDropdown.style.display = 'block';
            } else {
                vinDropdown.style.display = 'none';
            }
        });
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (vinDropdown && vinDropdown.style.display === 'block' && !e.target.closest('.avatar-dropdown-container')) {
            vinDropdown.style.display = 'none';
        }
    });

    // New Chat Button Handler
    const newChatBtn = document.getElementById('new-chat-btn');
    const chatHistoryList = document.getElementById('chat-history-list');
    
    // Store chat sessions in memory {id: string_html}
    const chatSessions = {};
    let currentSessionId = 'session-' + Date.now();
    let initialWelcomeHTML = chatContainer.innerHTML; // save the default state
    
    // Auto-save the current session state when DOM changes (a bit hacky but works cleanly for this scale)
    const observer = new MutationObserver(() => {
        chatSessions[currentSessionId] = chatContainer.innerHTML;
    });
    observer.observe(chatContainer, { childList: true, subtree: true });
    
    if (newChatBtn) {
        newChatBtn.addEventListener('click', () => {
            const userMessages = chatContainer.querySelectorAll('.user-message p');
            // If the current chat has at least one user message and isn't already saved as a li
            if (userMessages.length > 0 && !document.querySelector(`li[data-id="${currentSessionId}"]`)) {
                const title = userMessages[0].textContent.trim();
                
                // Add to history list UI
                const li = document.createElement('li');
                li.className = 'history-item';
                li.textContent = title;
                li.setAttribute('data-id', currentSessionId);
                
                // Add click listener to restore session
                li.addEventListener('click', function() {
                    const sid = this.getAttribute('data-id');
                    if (chatSessions[sid]) {
                        currentSessionId = sid;
                        chatContainer.innerHTML = chatSessions[sid];
                        scrollToBottom();
                    }
                });
                
                chatHistoryList.insertBefore(li, chatHistoryList.firstChild);
            }

            // Generate a fresh session
            currentSessionId = 'session-' + Date.now();
            chatContainer.innerHTML = initialWelcomeHTML;
            chatSessions[currentSessionId] = initialWelcomeHTML;
            
            chatInput.value = '';
            chatInput.style.height = 'auto';
            chatInput.focus();
        });
    }

    // Handle Enter key (Shift+Enter for new line)
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    sendBtn.addEventListener('click', sendMessage);

    async function sendMessage() {
        const query = chatInput.value.trim();
        if (!query) return;

        // 1. Add User Message to UI
        appendUserMessage(query);
        chatInput.value = '';
        chatInput.style.height = 'auto';
        
        // Disable input while generating
        chatInput.disabled = true;
        sendBtn.disabled = true;
        statusIndicator.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> 管家调取数据中...';
        statusIndicator.style.color = '#f39c12';

        // 2. Add Assistant empty message buble with loading
        const msgId = 'msg-' + Date.now();
        appendAssistantContainer(msgId);
        
        const contentDiv = document.querySelector(`#${msgId} .markdown-body`);

        try {
            // 3. Fetch stream from API
            const contextualQuery = `（系统信息：当前用户的车架号/VIN已切换为${currentVIN}）\n${query}`;
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ query: contextualQuery })
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let fullText = "";
            let isFirstChunk = true;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                if (isFirstChunk) {
                    contentDiv.innerHTML = '';
                    isFirstChunk = false;
                }
                
                const chunkMessage = decoder.decode(value, { stream: true });
                fullText += chunkMessage;
                
                // Parse markdown and update DOM
                contentDiv.innerHTML = marked.parse(fullText);
                scrollToBottom();
            }

        } catch (error) {
            console.error('Error:', error);
            contentDiv.innerHTML = `<p style="color: #e74c3c;"><i class="fa-solid fa-triangle-exclamation"></i> 抱歉，车服管家连接服务器失败，请检查网络或后台服务。</p>`;
        } finally {
            // Re-enable input
            chatInput.disabled = false;
            sendBtn.disabled = false;
            chatInput.focus();
            statusIndicator.innerHTML = '● 在线服务';
            statusIndicator.style.color = 'var(--accent-primary)';
        }
    }

    function appendUserMessage(text) {
        const div = document.createElement('div');
        div.className = 'message user-message entrance-anim';
        div.innerHTML = `
            <div class="msg-avatar"><i class="fa-solid fa-user"></i></div>
            <div class="msg-content glass-bubble">
                <p>${escapeHTML(text)}</p>
            </div>
        `;
        chatContainer.appendChild(div);
        scrollToBottom();
    }

    function appendAssistantContainer(id) {
        const div = document.createElement('div');
        div.className = 'message assistant-message entrance-anim';
        div.id = id;
        div.innerHTML = `
            <div class="msg-avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="msg-content glass-bubble markdown-body">
                <span class="thinking-text"><i class="fa-solid fa-microchip"></i> AI 管家正在思考</span>
            </div>
        `;
        chatContainer.appendChild(div);
        scrollToBottom();
    }

    function scrollToBottom() {
        chatContainer.scrollTo({
            top: chatContainer.scrollHeight,
            behavior: 'smooth'
        });
    }

    function escapeHTML(str) {
        return str.replace(/[&<>'"]/g, 
            tag => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                "'": '&#39;',
                '"': '&quot;'
            }[tag] || tag)
        );
    }
});
