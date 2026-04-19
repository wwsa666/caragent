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
            this.style.height = 'auto';
        }
    });

    // ========== User Profile Switcher ==========
    const userProfileBtn = document.getElementById('user-profile-btn');
    const currentUsername = document.getElementById('current-username');
    const vinDropdown = document.getElementById('vin-dropdown');
    const vinList = document.getElementById('vin-list');

    const availableVINs = ["VIN1001", "VIN1002", "VIN1003", "VIN1004", "VIN1005", "VIN1006", "VIN1007", "VIN1008", "VIN1009", "VIN1010"];
    
    if (vinList) {
        availableVINs.forEach(vin => {
            const li = document.createElement('li');
            li.textContent = vin;
            if (vin === currentVIN) li.classList.add('active');
            
            li.addEventListener('click', () => {
                currentVIN = vin;
                currentUsername.textContent = `${currentVIN} 车主`;
                document.querySelectorAll('#vin-list li').forEach(el => el.classList.remove('active'));
                li.classList.add('active');
                const welcomeP = document.querySelectorAll('.assistant-message .glass-bubble p');
                welcomeP.forEach(p => {
                    if (p.innerHTML.includes('您可以尝试回复')) {
                        p.innerHTML = `请问今天有什么可以帮您的？您可以尝试回复："*我是${currentVIN}车主，帮我查一下我2月的运行报告并给出保养建议*"`;
                    }
                });
                statusIndicator.innerHTML = `● 已切至 ${currentVIN}`;
                vinDropdown.style.display = 'none';
            });
            vinList.appendChild(li);
        });
    }

    if (userProfileBtn) {
        userProfileBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            vinDropdown.style.display = vinDropdown.style.display === 'block' ? 'none' : 'block';
        });
    }

    document.addEventListener('click', (e) => {
        if (vinDropdown && vinDropdown.style.display === 'block' && !e.target.closest('.avatar-dropdown-container')) {
            vinDropdown.style.display = 'none';
        }
    });

    // ========== New Chat ==========
    const newChatBtn = document.getElementById('new-chat-btn');
    const chatHistoryList = document.getElementById('chat-history-list');
    const chatSessions = {};
    let currentSessionId = 'session-' + Date.now();
    let initialWelcomeHTML = chatContainer.innerHTML;
    
    const observer = new MutationObserver(() => {
        chatSessions[currentSessionId] = chatContainer.innerHTML;
    });
    observer.observe(chatContainer, { childList: true, subtree: true });
    
    if (newChatBtn) {
        newChatBtn.addEventListener('click', () => {
            const userMessages = chatContainer.querySelectorAll('.user-message p');
            if (userMessages.length > 0 && !document.querySelector(`li[data-id="${currentSessionId}"]`)) {
                const title = userMessages[0].textContent.trim();
                const li = document.createElement('li');
                li.className = 'history-item';
                li.textContent = title;
                li.setAttribute('data-id', currentSessionId);
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
            currentSessionId = 'session-' + Date.now();
            chatContainer.innerHTML = initialWelcomeHTML;
            chatSessions[currentSessionId] = initialWelcomeHTML;
            chatInput.value = '';
            chatInput.style.height = 'auto';
            chatInput.focus();
        });
    }

    // ========== Chat Input ==========
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

        appendUserMessage(query);
        chatInput.value = '';
        chatInput.style.height = 'auto';

        // 检测报告意图：如果用户输入包含"报告"相关关键词，走 LangGraph 流程
        const reportKeywords = ['报告', '报表', '月报', '总结报告', '车况报告', '运行报告'];
        const isReportIntent = reportKeywords.some(kw => query.includes(kw));

        if (isReportIntent) {
            await startReportFlow();
        } else {
            await normalChat(query);
        }
    }

    // ========== 普通对话 ==========
    async function normalChat(query) {
        chatInput.disabled = true;
        sendBtn.disabled = true;
        statusIndicator.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> 管家调取数据中...';
        statusIndicator.style.color = '#f39c12';

        const msgId = 'msg-' + Date.now();
        appendAssistantContainer(msgId);
        const contentDiv = document.querySelector(`#${msgId} .markdown-body`);

        try {
            const contextualQuery = `（系统信息：当前用户的车架号/VIN已切换为${currentVIN}）\n${query}`;
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: contextualQuery })
            });

            if (!response.ok) throw new Error('Network response was not ok');

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let fullText = "";
            let isFirstChunk = true;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                if (isFirstChunk) { contentDiv.innerHTML = ''; isFirstChunk = false; }
                fullText += decoder.decode(value, { stream: true });
                contentDiv.innerHTML = marked.parse(fullText);
                scrollToBottom();
            }
        } catch (error) {
            console.error('Error:', error);
            contentDiv.innerHTML = `<p style="color: #e74c3c;"><i class="fa-solid fa-triangle-exclamation"></i> 抱歉，车服管家连接服务器失败。</p>`;
        } finally {
            chatInput.disabled = false;
            sendBtn.disabled = false;
            chatInput.focus();
            statusIndicator.innerHTML = '● 在线服务';
            statusIndicator.style.color = 'var(--accent-primary)';
        }
    }

    // ========== LangGraph 报告工作流 (interrupt + resume) ==========

    async function startReportFlow() {
        chatInput.disabled = true;
        sendBtn.disabled = true;
        statusIndicator.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> LangGraph 工作流启动中...';
        statusIndicator.style.color = '#f39c12';

        const msgId = 'msg-' + Date.now();
        appendAssistantContainer(msgId);
        const contentDiv = document.querySelector(`#${msgId} .markdown-body`);

        try {
            // Phase 1: POST /api/report/start → 触发 interrupt → 秒回
            const startResp = await fetch('/api/report/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ vin: currentVIN })
            });

            if (!startResp.ok) throw new Error('start API error');
            const startData = await startResp.json();

            if (startData.type !== 'interrupt' || !startData.payload) {
                throw new Error('unexpected response from start API');
            }

            const threadId = startData.thread_id;
            const payload = startData.payload;

            // 渲染 AI 提问 + 选项卡片到聊天气泡里
            contentDiv.innerHTML = renderInterruptOptions(payload, threadId);
            scrollToBottom();

            // 恢复输入（用户需要点击卡片来操作）
            statusIndicator.innerHTML = '● 等待您选择报告配置...';
            statusIndicator.style.color = 'var(--accent-primary)';
            chatInput.disabled = false;
            sendBtn.disabled = false;

        } catch (error) {
            console.error('Report Start Error:', error);
            contentDiv.innerHTML = `<p style="color: #e74c3c;"><i class="fa-solid fa-triangle-exclamation"></i> 报告工作流启动失败，请确认 MongoDB 已启动。</p>`;
            chatInput.disabled = false;
            sendBtn.disabled = false;
            statusIndicator.innerHTML = '● 在线服务';
            statusIndicator.style.color = 'var(--accent-primary)';
        }
    }

    /** 将 interrupt 的 payload 渲染为可交互的选项卡片 HTML */
    function renderInterruptOptions(payload, threadId) {
        let html = `<p><strong>📊 ${payload.question}</strong></p>`;
        html += `<div class="report-options-container" data-thread-id="${threadId}">`;

        // 时间范围（单选）
        html += `<div class="report-section-title">📅 时间范围（单选）</div>`;
        html += `<div class="report-option-group" data-group="time_range">`;
        payload.time_range_options.forEach((opt, i) => {
            const selected = i === 0 ? ' selected' : '';
            html += `<div class="report-option-card${selected}" data-value="${opt.value}">${opt.label}</div>`;
        });
        html += `</div>`;

        // 月份选择器
        html += `<div class="report-month-picker">`;
        html += `<select class="report-month-select" data-group="month">`;
        payload.month_options.forEach(opt => {
            const sel = opt.value === '2025-02' ? ' selected' : '';
            html += `<option value="${opt.value}"${sel}>${opt.label}</option>`;
        });
        html += `</select></div>`;

        // 维度（多选）
        html += `<div class="report-section-title">🔍 分析维度（可多选）</div>`;
        html += `<div class="report-option-group" data-group="dimensions">`;
        payload.dimension_options.forEach((opt, i) => {
            const selected = i < 3 ? ' selected' : '';  // 默认选前3个
            const icon = opt.icon ? `<i class="${opt.icon}"></i> ` : '';
            html += `<div class="report-option-card${selected}" data-value="${opt.value}">${icon}${opt.label}</div>`;
        });
        html += `</div>`;

        // 确认按钮
        html += `<button class="report-confirm-btn" data-thread-id="${threadId}"><i class="fa-solid fa-paper-plane"></i> 确认生成</button>`;
        html += `</div>`;
        return html;
    }

    // 事件委托：处理聊天区域内的报告选项点击
    chatContainer.addEventListener('click', (e) => {
        const card = e.target.closest('.report-option-card');
        const confirmBtn = e.target.closest('.report-confirm-btn');

        if (card) {
            const group = card.parentElement;
            const groupType = group.getAttribute('data-group');

            if (groupType === 'time_range') {
                // 单选逻辑
                group.querySelectorAll('.report-option-card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');

                // 控制月份选择器显示
                const container = card.closest('.report-options-container');
                const monthPicker = container.querySelector('.report-month-picker');
                if (card.getAttribute('data-value') === 'single_month') {
                    monthPicker.style.display = 'block';
                } else {
                    monthPicker.style.display = 'none';
                }
            } else if (groupType === 'dimensions') {
                // 多选逻辑
                card.classList.toggle('selected');
            }
        }

        if (confirmBtn) {
            handleReportConfirm(confirmBtn);
        }
    });

    /** 用户点击"确认生成"后，收集选择 → resume 工作流 */
    async function handleReportConfirm(btn) {
        const threadId = btn.getAttribute('data-thread-id');
        const container = btn.closest('.report-options-container');

        // 收集用户选择
        const timeRangeGroup = container.querySelector('[data-group="time_range"]');
        const selectedTimeRange = timeRangeGroup.querySelector('.selected')?.getAttribute('data-value') || 'single_month';

        const monthSelect = container.querySelector('.report-month-select');
        const selectedMonth = monthSelect ? monthSelect.value : '2025-02';

        const dimGroup = container.querySelector('[data-group="dimensions"]');
        const selectedDimensions = [];
        dimGroup.querySelectorAll('.selected').forEach(c => {
            selectedDimensions.push(c.getAttribute('data-value'));
        });

        if (selectedDimensions.length === 0) {
            alert('请至少选择一个分析维度！');
            return;
        }

        // 禁用按钮和选项，防止重复提交
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> 生成中...';
        container.querySelectorAll('.report-option-card').forEach(c => c.style.pointerEvents = 'none');

        // 构建用户选择摘要
        const dimLabels = {
            driving_habit: '驾驶习惯', energy: '能耗水平', battery: '电池健康',
            mileage: '行驶里程', duration: '驾驶时长'
        };
        const timeLabels = {
            single_month: '单月', quarter: '季度', half_year: '半年', full_year: '全年'
        };
        const timeDesc = selectedTimeRange === 'single_month' ? `${selectedMonth} 单月` : timeLabels[selectedTimeRange];
        const dimDesc = selectedDimensions.map(d => dimLabels[d] || d).join('、');

        appendUserMessage(`✅ 已选择：${timeDesc}报告，维度 → ${dimDesc}`);

        // Phase 2: 显示思考状态 + resume
        chatInput.disabled = true;
        sendBtn.disabled = true;
        statusIndicator.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> LangGraph 读档恢复中...';
        statusIndicator.style.color = '#f39c12';

        const reportMsgId = 'msg-' + Date.now();
        appendAssistantContainer(reportMsgId);
        const reportContentDiv = document.querySelector(`#${reportMsgId} .markdown-body`);

        try {
            const resumeResp = await fetch('/api/report/resume', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    thread_id: threadId,
                    answer: {
                        time_range: selectedTimeRange,
                        month: selectedMonth,
                        dimensions: selectedDimensions,
                    }
                })
            });

            if (!resumeResp.ok) throw new Error('Resume API error');

            const reader = resumeResp.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let fullText = '';
            let isFirstChunk = true;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                if (isFirstChunk) { reportContentDiv.innerHTML = ''; isFirstChunk = false; }
                fullText += decoder.decode(value, { stream: true });
                reportContentDiv.innerHTML = marked.parse(fullText);
                scrollToBottom();
            }
        } catch (error) {
            console.error('Resume Error:', error);
            reportContentDiv.innerHTML = `<p style="color: #e74c3c;"><i class="fa-solid fa-triangle-exclamation"></i> 报告恢复生成失败。</p>`;
        } finally {
            chatInput.disabled = false;
            sendBtn.disabled = false;
            chatInput.focus();
            statusIndicator.innerHTML = '● 在线服务';
            statusIndicator.style.color = 'var(--accent-primary)';
        }
    }

    // ========== Report Button (Header) ==========
    const openReportBtn = document.getElementById('open-report-btn');
    if (openReportBtn) {
        openReportBtn.addEventListener('click', () => {
            appendUserMessage('📊 请为我的爱车生成定制报告');
            startReportFlow();
        });
    }

    // ========== Utility Functions ==========
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
        chatContainer.scrollTo({ top: chatContainer.scrollHeight, behavior: 'smooth' });
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
