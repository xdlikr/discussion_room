// API基础URL
const API_BASE = '/api';

// 全局状态
let currentDiscussionId = null;
let currentAgents = [];
let availableModels = [];
let isProcessing = false;
let editingAgentId = null;
let currentAbortController = null;  // 用于中断请求
let isPaused = false;

// DOM元素（延迟初始化）
let elements = {};

// 初始化DOM元素引用
function initElements() {
    elements = {
        agentsList: document.getElementById('agentsList'),
        discussionsList: document.getElementById('discussionsList'),
        messagesContainer: document.getElementById('messagesContainer'),
        welcomeScreen: document.getElementById('welcomeScreen'),
        messageInput: document.getElementById('messageInput'),
        sendBtn: document.getElementById('sendBtn'),
        sendBtnText: document.getElementById('sendBtnText'),
        addAgentBtn: document.getElementById('addAgentBtn'),
        newDiscussionBtn: document.getElementById('newDiscussionBtn'),
        summarizeBtn: document.getElementById('summarizeBtn'),
    stopBtn: document.getElementById('stopBtn'),
    resumeBtn: document.getElementById('resumeBtn'),
    enhanceBtn: document.getElementById('enhanceBtn'),
    currentTopic: document.getElementById('currentTopic'),
        agentModal: document.getElementById('agentModal'),
        agentForm: document.getElementById('agentForm'),
        closeModalBtn: document.getElementById('closeModalBtn'),
        cancelBtn: document.getElementById('cancelBtn'),
        modalTitle: document.getElementById('modalTitle'),
        agentName: document.getElementById('agentName'),
        agentRole: document.getElementById('agentRole'),
        agentPrompt: document.getElementById('agentPrompt'),
        agentModel: document.getElementById('agentModel'),
        agentAutocomplete: document.getElementById('agentAutocomplete')
    };
}

// 初始化应用
async function init() {
    try {
        // 初始化DOM元素
        initElements();
        
        // 检查关键元素
        const missingElements = [];
        if (!elements.sendBtn) missingElements.push('sendBtn');
        if (!elements.messageInput) missingElements.push('messageInput');
        if (!elements.addAgentBtn) missingElements.push('addAgentBtn');
        if (!elements.newDiscussionBtn) missingElements.push('newDiscussionBtn');
        
        if (missingElements.length > 0) {
            console.error('关键DOM元素未找到:', missingElements);
            console.error('请确保页面完全加载后再初始化');
            // 延迟重试
            setTimeout(init, 100);
            return;
        }
        
        console.log('✓ DOM元素初始化完成');
        
        // 配置marked.js
        if (typeof marked !== 'undefined') {
            marked.setOptions({
                breaks: true,  // 支持GFM换行
                gfm: true,     // 启用GitHub风格Markdown
                tables: true,  // 支持表格
                sanitize: false, // 不过滤HTML（我们会用DOMPurify或者信任AI输出）
                headerIds: false,
                mangle: false
            });
            console.log('✓ Marked.js配置完成');
        } else {
            console.warn('⚠ Marked.js未加载');
        }
        
        console.log('开始加载数据...');
        await loadModels();
        await loadAgents();
        await loadDiscussions();
        
        console.log('设置事件监听器...');
        setupEventListeners();
        
        console.log('✓ 应用初始化完成');
    } catch (error) {
        console.error('初始化失败:', error);
        alert('应用初始化失败: ' + error.message);
    }
}

// 设置事件监听
function setupEventListeners() {
    if (elements.sendBtn) {
        elements.sendBtn.addEventListener('click', handleSendMessage);
    }
    
    if (elements.messageInput) {
        elements.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
            }
        });
        
        // @自动完成
        elements.messageInput.addEventListener('input', handleAutocomplete);
        elements.messageInput.addEventListener('keydown', handleAutocompleteKeydown);
    }
    
    if (elements.addAgentBtn) {
        elements.addAgentBtn.addEventListener('click', () => openAgentModal());
    }
    
    if (elements.newDiscussionBtn) {
        elements.newDiscussionBtn.addEventListener('click', startNewDiscussion);
    }
    
    if (elements.summarizeBtn) {
        elements.summarizeBtn.addEventListener('click', generateSummary);
    }
    
    if (elements.stopBtn) {
        elements.stopBtn.addEventListener('click', stopDiscussion);
    }
    
    if (elements.resumeBtn) {
        elements.resumeBtn.addEventListener('click', resumeDiscussion);
    }
    
    if (elements.enhanceBtn) {
        elements.enhanceBtn.addEventListener('click', triggerDataEnhancement);
    }
    
    if (elements.closeModalBtn) {
        elements.closeModalBtn.addEventListener('click', closeAgentModal);
    }
    
    if (elements.cancelBtn) {
        elements.cancelBtn.addEventListener('click', closeAgentModal);
    }
    
    if (elements.agentForm) {
        elements.agentForm.addEventListener('submit', handleAgentSubmit);
    }
    
    // 点击模态框外部关闭
    if (elements.agentModal) {
        elements.agentModal.addEventListener('click', (e) => {
            if (e.target === elements.agentModal) {
                closeAgentModal();
            }
        });
    }
    
    // 点击外部关闭自动完成
    document.addEventListener('click', (e) => {
        if (elements.messageInput && elements.agentAutocomplete && 
            e.target !== elements.messageInput && e.target !== elements.agentAutocomplete) {
            hideAutocomplete();
        }
    });
}

// ===== Agent管理 =====

async function loadModels() {
    try {
        const response = await fetch(`${API_BASE}/agents/models/available`);
        availableModels = await response.json();
        renderModelOptions();
    } catch (error) {
        console.error('加载模型列表失败:', error);
        availableModels = [
            {id: "Qwen/Qwen2.5-7B-Instruct", name: "Qwen2.5-7B-Instruct", provider: "Qwen"}
        ];
        renderModelOptions();
    }
}

function renderModelOptions() {
    if (!elements.agentModel) return;
    
    elements.agentModel.innerHTML = availableModels.map(model => `
        <option value="${model.id}">${model.name} (${model.provider})</option>
    `).join('');
}

async function loadAgents() {
    try {
        const response = await fetch(`${API_BASE}/agents`);
        currentAgents = await response.json();
        renderAgents();
    } catch (error) {
        console.error('加载Agent失败:', error);
        showError('加载分析师列表失败');
    }
}

function renderAgents() {
    if (currentAgents.length === 0) {
        elements.agentsList.innerHTML = '<p style="padding: 16px; color: var(--text-muted); text-align: center; font-size: 13px;">暂无分析师<br>点击 + 添加</p>';
        return;
    }
    
    elements.agentsList.innerHTML = currentAgents.map(agent => `
        <div class="agent-card" data-id="${agent.id}">
            <div class="agent-header">
                <span class="agent-name">${escapeHtml(agent.name)}</span>
                <div class="agent-actions">
                    <button class="btn-icon-small" onclick="editAgent(${agent.id})" title="编辑">✏️</button>
                    <button class="btn-icon-small" onclick="deleteAgent(${agent.id})" title="删除">🗑️</button>
                </div>
            </div>
            <div class="agent-role">${escapeHtml(agent.role)}</div>
            <div class="agent-model-selector">
                <label>🤖 模型:</label>
                <select class="model-quick-select" onchange="quickChangeModel(${agent.id}, this.value)" data-agent-id="${agent.id}">
                    ${availableModels.map(model => `
                        <option value="${model.id}" ${agent.model === model.id ? 'selected' : ''}>
                            ${model.name}
                        </option>
                    `).join('')}
                </select>
            </div>
        </div>
    `).join('');
}

function openAgentModal(agent = null) {
    editingAgentId = agent ? agent.id : null;
    
    if (agent) {
        elements.modalTitle.textContent = '编辑分析师';
        elements.agentName.value = agent.name;
        elements.agentRole.value = agent.role;
        elements.agentPrompt.value = agent.system_prompt;
        elements.agentModel.value = agent.model || 'Qwen/Qwen2.5-7B-Instruct';
    } else {
        elements.modalTitle.textContent = '添加分析师';
        elements.agentForm.reset();
        // 设置默认模型
        elements.agentModel.value = 'Qwen/Qwen2.5-7B-Instruct';
    }
    
    elements.agentModal.classList.add('show');
}

function closeAgentModal() {
    elements.agentModal.classList.remove('show');
    elements.agentForm.reset();
    editingAgentId = null;
}

async function handleAgentSubmit(e) {
    e.preventDefault();
    
    const data = {
        name: elements.agentName.value.trim(),
        role: elements.agentRole.value.trim(),
        system_prompt: elements.agentPrompt.value.trim(),
        model: elements.agentModel.value
    };
    
    try {
        if (editingAgentId) {
            // 更新
            await fetch(`${API_BASE}/agents/${editingAgentId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        } else {
            // 创建
            await fetch(`${API_BASE}/agents`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        }
        
        closeAgentModal();
        await loadAgents();
    } catch (error) {
        console.error('保存Agent失败:', error);
        showError('保存分析师失败');
    }
}

async function editAgent(id) {
    const agent = currentAgents.find(a => a.id === id);
    if (agent) {
        openAgentModal(agent);
    }
}

async function deleteAgent(id) {
    if (!confirm('确定要删除这个分析师吗？')) return;
    
    try {
        await fetch(`${API_BASE}/agents/${id}`, { method: 'DELETE' });
        await loadAgents();
    } catch (error) {
        console.error('删除Agent失败:', error);
        showError('删除分析师失败');
    }
}

async function quickChangeModel(agentId, newModel) {
    try {
        await fetch(`${API_BASE}/agents/${agentId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: newModel })
        });
        
        // 更新本地状态
        const agent = currentAgents.find(a => a.id === agentId);
        if (agent) {
            agent.model = newModel;
        }
    } catch (error) {
        console.error('切换模型失败:', error);
        showError('切换模型失败');
        await loadAgents(); // 重新加载以恢复状态
    }
}

async function loadDefaultTeam() {
    if (currentAgents.length > 0) {
        if (!confirm(`当前已有${currentAgents.length}个Agent，是否删除并加载默认专业团队？`)) {
            return;
        }
        
        // 删除所有现有Agent
        try {
            await fetch(`${API_BASE}/agents/all`, { method: 'DELETE' });
        } catch (error) {
            console.error('删除失败:', error);
            showError('删除现有Agent失败');
            return;
        }
    }
    
    try {
        const response = await fetch(`${API_BASE}/agents/init-defaults`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error('加载默认团队失败');
        }
        
        await loadAgents();
        alert('✅ 成功加载7个专业分析师团队！');
    } catch (error) {
        console.error('加载默认团队失败:', error);
        showError('加载默认团队失败');
    }
}

// ===== 讨论管理 =====

async function loadDiscussions() {
    try {
        const response = await fetch(`${API_BASE}/discussions`);
        const discussions = await response.json();
        renderDiscussions(discussions);
    } catch (error) {
        console.error('加载讨论历史失败:', error);
    }
}

function renderDiscussions(discussions) {
    if (discussions.length === 0) {
        elements.discussionsList.innerHTML = '<p style="padding: 16px; color: var(--text-muted); text-align: center; font-size: 13px;">暂无历史讨论</p>';
        return;
    }
    
    elements.discussionsList.innerHTML = discussions.map(discussion => `
        <div class="discussion-item ${discussion.id === currentDiscussionId ? 'active' : ''}" 
             onclick="loadDiscussion(${discussion.id})">
            <div class="discussion-topic">${escapeHtml(discussion.topic)}</div>
            <div class="discussion-date">${formatDate(discussion.created_at)}</div>
        </div>
    `).join('');
}

async function loadDiscussion(id) {
    try {
        const response = await fetch(`${API_BASE}/discussions/${id}`);
        const data = await response.json();
        
        currentDiscussionId = id;
        elements.currentTopic.textContent = data.discussion.topic;
        elements.welcomeScreen.style.display = 'none';
        
        // 显示消息
        renderMessages(data.messages);
        
        // 显示总结按钮
        if (data.discussion.status === 'completed' || data.messages.length > 0) {
            elements.summarizeBtn.style.display = 'block';
        }
        
        // 更新讨论列表样式
        await loadDiscussions();
        
        // 滚动到底部
        scrollToBottom();
    } catch (error) {
        console.error('加载讨论失败:', error);
        showError('加载讨论失败');
    }
}

function renderMessages(messages) {
    const messagesHtml = messages.map(msg => {
        if (msg.message_type === 'user') {
            return `
                <div class="message user">
                    <div class="message-header">
                        <div class="message-avatar">👤</div>
                        <div class="message-meta">
                            <div class="message-name">你</div>
                        </div>
                    </div>
                    <div class="message-content">${renderMarkdown(msg.content)}</div>
                </div>
            `;
        } else if (msg.message_type === 'agent') {
            return `
                <div class="message agent">
                    <div class="message-header">
                        <div class="message-avatar">${getAgentInitial(msg.agent_name)}</div>
                        <div class="message-meta">
                            <div class="message-name">${escapeHtml(msg.agent_name || 'Agent')}</div>
                            <div class="message-role">AI分析师</div>
                        </div>
                    </div>
                    <div class="message-content">${renderMarkdown(msg.content)}</div>
                </div>
            `;
        } else if (msg.message_type === 'summary') {
            return `
                <div class="message summary">
                    <div class="message-header">
                        <div class="message-avatar">📊</div>
                        <div class="message-meta">
                            <div class="message-name">智能总结</div>
                        </div>
                    </div>
                    <div class="message-content">${renderMarkdown(msg.content)}</div>
                </div>
            `;
        }
        return '';
    }).join('');
    
    elements.messagesContainer.innerHTML = messagesHtml;
}

function startNewDiscussion() {
    currentDiscussionId = null;
    elements.currentTopic.textContent = '开始新的讨论';
    elements.messagesContainer.innerHTML = '<div class="welcome-screen" id="welcomeScreen" style="display: flex;"><div class="welcome-content"><h1>欢迎使用 Opinion Room</h1><p>多智能体AI讨论平台</p><div class="welcome-steps"><div class="step"><div class="step-number">1</div><p>添加AI分析师并定义他们的角色</p></div><div class="step"><div class="step-number">2</div><p>输入投资话题开始讨论</p></div><div class="step"><div class="step-number">3</div><p>观看AI分析师们的精彩讨论</p></div></div></div></div>';
    elements.welcomeScreen = document.getElementById('welcomeScreen');
    elements.summarizeBtn.style.display = 'none';
    elements.messageInput.value = '';
    elements.sendBtnText.textContent = '开始讨论';
    
    // 更新讨论列表样式
    loadDiscussions();
}

// ===== 消息发送 =====

async function handleSendMessage() {
    if (isProcessing) return;
    
    const content = elements.messageInput.value.trim();
    if (!content) return;
    
    if (currentAgents.length === 0) {
        showError('请先添加至少一个分析师');
        return;
    }
    
    // 检查是否是@提及
    const mentionMatch = content.match(/^@([^\s]+)\s+(.+)/);
    if (mentionMatch) {
        await handleMentionMessage(mentionMatch[1], mentionMatch[2]);
        return;
    }
    
    // 禁用输入
    isProcessing = true;
    elements.sendBtn.disabled = true;
    elements.messageInput.disabled = true;
    elements.sendBtnText.textContent = '讨论中...';
    
    try {
        if (!currentDiscussionId) {
            // 创建新讨论
            const response = await fetch(`${API_BASE}/discussions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic: content })
            });
            const discussion = await response.json();
            currentDiscussionId = discussion.id;
            elements.currentTopic.textContent = discussion.topic;
            elements.welcomeScreen.style.display = 'none';
            
            // 开始讨论
            await streamDiscussion('start');
        } else {
            // 继续讨论
            await streamDiscussion('continue', content);
        }
        
        elements.messageInput.value = '';
        elements.sendBtnText.textContent = '继续提问';
        elements.summarizeBtn.style.display = 'block';
        await loadDiscussions();
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('请求已中断');
            // 不显示错误，因为这是用户主动停止
        } else {
            console.error('发送消息失败:', error);
            showError('发送消息失败：' + error.message);
        }
    } finally {
        isProcessing = false;
        elements.sendBtn.disabled = false;
        elements.messageInput.disabled = false;
        elements.stopBtn.style.display = 'none';
        currentAbortController = null;
    }
}

async function handleMentionMessage(agentName, question) {
    // 查找Agent（支持部分匹配）
    const agent = currentAgents.find(a => 
        a.name.includes(agentName) || agentName.includes(a.name.split(' ')[0])
    );
    
    if (!agent) {
        showError(`未找到Agent: ${agentName}`);
        return;
    }
    
    // 如果没有当前讨论，先创建
    if (!currentDiscussionId) {
        try {
            const response = await fetch(`${API_BASE}/discussions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic: `@${agent.name} ${question}` })
            });
            const discussion = await response.json();
            currentDiscussionId = discussion.id;
            elements.currentTopic.textContent = discussion.topic;
            elements.welcomeScreen.style.display = 'none';
        } catch (error) {
            console.error('创建讨论失败:', error);
            showError('创建讨论失败');
            return;
        }
    }
    
    // 禁用输入
    isProcessing = true;
    elements.sendBtn.disabled = true;
    elements.messageInput.disabled = true;
    elements.sendBtnText.textContent = '等待回复...';
    
    try {
        await askSpecificAgent(agent.id, question);
        elements.messageInput.value = '';
        elements.sendBtnText.textContent = '继续提问';
        await loadDiscussions();
    } catch (error) {
        console.error('@提及失败:', error);
        showError('@提及失败：' + error.message);
    } finally {
        isProcessing = false;
        elements.sendBtn.disabled = false;
        elements.messageInput.disabled = false;
    }
}

async function askSpecificAgent(agentId, content) {
    const response = await fetch(`${API_BASE}/discussions/${currentDiscussionId}/ask-agent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: agentId, content })
    });
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    let currentAgentId = null;
    let currentMessageDiv = null;
    let currentContentDiv = null;
    let currentRawContent = '';
    
    // 先显示用户消息
    const agent = currentAgents.find(a => a.id === agentId);
    if (agent) {
        appendUserMessage(`@${agent.name} ${content}`);
    }
    
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        
        for (const line of lines) {
            if (line.startsWith('data: ')) {
                try {
                    const data = JSON.parse(line.slice(6));
                    
                    if (data.type === 'agent_start') {
                        currentAgentId = data.agent_id;
                        currentRawContent = '';
                        currentMessageDiv = appendAgentMessage(data.agent_name, data.agent_role);
                        currentContentDiv = currentMessageDiv.querySelector('.message-content');
                        currentContentDiv.innerHTML = '<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>';
                    } else if (data.type === 'content' && currentContentDiv) {
                        const typingIndicator = currentContentDiv.querySelector('.typing-indicator');
                        if (typingIndicator) {
                            typingIndicator.remove();
                        }
                        
                        currentRawContent += data.content;
                        currentContentDiv.innerHTML = renderMarkdown(currentRawContent);
                        scrollToBottom();
                    } else if (data.type === 'agent_end') {
                        currentAgentId = null;
                        currentContentDiv = null;
                        currentRawContent = '';
                    } else if (data.type === 'error') {
                        if (currentContentDiv) {
                            currentContentDiv.textContent = '错误: ' + data.message;
                        }
                    }
                } catch (e) {
                    console.error('解析SSE数据失败:', e);
                }
            }
        }
    }
}

async function streamDiscussion(action, content = null) {
    const url = action === 'start' 
        ? `${API_BASE}/discussions/${currentDiscussionId}/start`
        : `${API_BASE}/discussions/${currentDiscussionId}/continue`;
    
    const options = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    };
    
    if (action === 'continue') {
        options.body = JSON.stringify({ content });
        
        // 先显示用户消息
        appendUserMessage(content);
    }
    
    // 创建AbortController用于中断
    currentAbortController = new AbortController();
    options.signal = currentAbortController.signal;
    
    // 显示停止按钮
    elements.stopBtn.style.display = 'block';
    elements.resumeBtn.style.display = 'none';
    isPaused = false;
    
    try {
        const response = await fetch(url, options);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let currentAgentId = null;
        let currentMessageDiv = null;
        let currentContentDiv = null;
        let currentRawContent = '';  // 累积原始文本用于Markdown渲染
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.type === 'debate_starting') {
                            // 显示辩论开始提示
                            const debateDiv = document.createElement('div');
                            debateDiv.className = 'debate-separator';
                            debateDiv.innerHTML = '<div class="debate-label">💬 开始辩论讨论</div>';
                            elements.messagesContainer.appendChild(debateDiv);
                            scrollToBottom();
                        } else if (data.type === 'round_start') {
                            // 显示轮次开始
                            const roundDiv = document.createElement('div');
                            roundDiv.className = 'round-separator';
                            roundDiv.innerHTML = `<div class="round-label">第 ${data.round} 轮辩论</div>`;
                            elements.messagesContainer.appendChild(roundDiv);
                            scrollToBottom();
                        } else if (data.type === 'round_end') {
                            // 轮次结束，可以添加分隔线
                    } else if (data.type === 'debate_done') {
                        // 辩论结束，显示数据增强按钮提示
                        const doneDiv = document.createElement('div');
                        doneDiv.className = 'debate-separator';
                        doneDiv.innerHTML = '<div class="debate-label">💬 辩论讨论完成。点击"数据增强"按钮获取实时股票数据验证分析。</div>';
                        elements.messagesContainer.appendChild(doneDiv);
                        scrollToBottom();
                        // 显示数据增强按钮
                        elements.enhanceBtn.style.display = 'block';
                        } else if (data.type === 'enhance_done') {
                            // 数据增强完成
                            const doneDiv = document.createElement('div');
                            doneDiv.className = 'debate-separator';
                            doneDiv.innerHTML = '<div class="debate-label">✅ 数据增强分析完成</div>';
                            elements.messagesContainer.appendChild(doneDiv);
                            scrollToBottom();
                        } else if (data.type === 'data_loaded') {
                            // 数据加载完成
                            const dataDiv = document.createElement('div');
                            dataDiv.className = 'debate-separator';
                            dataDiv.innerHTML = `<div class="debate-label">📊 已加载实时数据: ${data.symbols.join(', ')}</div>`;
                            elements.messagesContainer.appendChild(dataDiv);
                            scrollToBottom();
                        } else if (data.type === 'agent_start') {
                            currentAgentId = data.agent_id;
                            currentRawContent = '';  // 重置累积内容
                            const roundInfo = data.round ? ` (第${data.round}轮)` : '';
                            currentMessageDiv = appendAgentMessage(data.agent_name, data.agent_role + roundInfo);
                            currentContentDiv = currentMessageDiv.querySelector('.message-content');
                            currentContentDiv.innerHTML = '<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>';
                        } else if (data.type === 'content' && currentContentDiv) {
                            // 移除加载动画
                            const typingIndicator = currentContentDiv.querySelector('.typing-indicator');
                            if (typingIndicator) {
                                typingIndicator.remove();
                            }
                            
                            // 累积内容并重新渲染Markdown
                            currentRawContent += data.content;
                            currentContentDiv.innerHTML = renderMarkdown(currentRawContent);
                            scrollToBottom();
                        } else if (data.type === 'agent_end') {
                            currentAgentId = null;
                            currentContentDiv = null;
                            currentRawContent = '';
                        } else if (data.type === 'error') {
                            if (currentContentDiv) {
                                currentContentDiv.textContent = '错误: ' + data.message + ' (正在重试...)';
                            }
                        }
                    } catch (e) {
                        console.error('解析SSE数据失败:', e);
                    }
                }
            }
        }
    } catch (error) {
        console.error('流式请求失败:', error);
        if (error.name !== 'AbortError') {
            showError('请求失败: ' + error.message);
        }
        // 隐藏停止按钮
        elements.stopBtn.style.display = 'none';
        elements.resumeBtn.style.display = 'none';
    }
}

function appendUserMessage(content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user';
    messageDiv.innerHTML = `
        <div class="message-header">
            <div class="message-avatar">👤</div>
            <div class="message-meta">
                <div class="message-name">你</div>
            </div>
        </div>
        <div class="message-content">${renderMarkdown(content)}</div>
    `;
    elements.messagesContainer.appendChild(messageDiv);
    scrollToBottom();
}

function appendAgentMessage(name, role) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message agent';
    messageDiv.innerHTML = `
        <div class="message-header">
            <div class="message-avatar">${getAgentInitial(name)}</div>
            <div class="message-meta">
                <div class="message-name">${escapeHtml(name)}</div>
                <div class="message-role">${escapeHtml(role)}</div>
            </div>
        </div>
        <div class="message-content"></div>
    `;
    elements.messagesContainer.appendChild(messageDiv);
    scrollToBottom();
    return messageDiv;
}

// ===== 生成总结 =====

async function generateSummary() {
    if (!currentDiscussionId || isProcessing) return;
    
    isProcessing = true;
    elements.summarizeBtn.disabled = true;
    elements.summarizeBtn.textContent = '生成中...';
    
    try {
        const response = await fetch(`${API_BASE}/discussions/${currentDiscussionId}/summarize`, {
            method: 'POST'
        });
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        // 创建总结消息
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message summary';
        messageDiv.innerHTML = `
            <div class="message-header">
                <div class="message-avatar">📊</div>
                <div class="message-meta">
                    <div class="message-name">智能总结</div>
                </div>
            </div>
            <div class="message-content"><div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div></div>
        `;
        elements.messagesContainer.appendChild(messageDiv);
        const contentDiv = messageDiv.querySelector('.message-content');
        scrollToBottom();
        
        let summaryContent = '';  // 累积总结内容
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.type === 'content') {
                            // 移除加载动画
                            const typingIndicator = contentDiv.querySelector('.typing-indicator');
                            if (typingIndicator) {
                                typingIndicator.remove();
                            }
                            
                            // 累积内容并重新渲染Markdown
                            summaryContent += data.content;
                            contentDiv.innerHTML = renderMarkdown(summaryContent);
                            scrollToBottom();
                        }
                    } catch (e) {
                        console.error('解析SSE数据失败:', e);
                    }
                }
            }
        }
        
        elements.summarizeBtn.textContent = '生成总结';
    } catch (error) {
        console.error('生成总结失败:', error);
        showError('生成总结失败');
    } finally {
        isProcessing = false;
        elements.summarizeBtn.disabled = false;
    }
}

// ===== 工具函数 =====

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderMarkdown(text) {
    if (typeof marked === 'undefined') {
        return escapeHtml(text);
    }
    try {
        return marked.parse(text);
    } catch (e) {
        console.error('Markdown解析失败:', e);
        return escapeHtml(text);
    }
}

function getAgentInitial(name) {
    return name ? name.charAt(0).toUpperCase() : 'A';
}

function getModelShortName(modelId) {
    if (!modelId) return 'Unknown';
    // 从完整的模型ID中提取短名称
    const parts = modelId.split('/');
    return parts.length > 1 ? parts[1] : modelId;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) return '刚刚';
    if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前';
    if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前';
    
    return date.toLocaleDateString('zh-CN', { 
        month: 'short', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function scrollToBottom() {
    setTimeout(() => {
        elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
    }, 100);
}

function showError(message) {
    alert(message); // 简单实现，可以改为更优雅的提示
}

// ===== @自动完成功能 =====

let autocompleteIndex = -1;
let filteredAgents = [];

function handleAutocomplete(e) {
    const value = elements.messageInput.value;
    const cursorPos = elements.messageInput.selectionStart;
    
    // 检查是否输入@
    const textBeforeCursor = value.substring(0, cursorPos);
    const mentionMatch = textBeforeCursor.match(/@([^\s]*)$/);
    
    if (mentionMatch) {
        const query = mentionMatch[1].toLowerCase();
        
        // 过滤Agent
        filteredAgents = currentAgents.filter(agent => 
            agent.name.toLowerCase().includes(query)
        );
        
        if (filteredAgents.length > 0) {
            showAutocomplete(filteredAgents);
        } else {
            hideAutocomplete();
        }
    } else {
        hideAutocomplete();
    }
}

function showAutocomplete(agents) {
    const rect = elements.messageInput.getBoundingClientRect();
    elements.agentAutocomplete.style.display = 'block';
    elements.agentAutocomplete.style.bottom = `calc(100% - ${rect.top}px + 8px)`;
    elements.agentAutocomplete.style.left = `${rect.left}px`;
    elements.agentAutocomplete.style.width = `${rect.width}px`;
    
    elements.agentAutocomplete.innerHTML = agents.map((agent, index) => `
        <div class="autocomplete-item ${index === autocompleteIndex ? 'active' : ''}" 
             onclick="selectAgent('${agent.name}')">
            <span class="agent-name">${escapeHtml(agent.name)}</span>
            <span class="agent-role-small">${escapeHtml(agent.role)}</span>
        </div>
    `).join('');
    
    autocompleteIndex = -1;
}

function hideAutocomplete() {
    elements.agentAutocomplete.style.display = 'none';
    autocompleteIndex = -1;
    filteredAgents = [];
}

function handleAutocompleteKeydown(e) {
    if (elements.agentAutocomplete.style.display === 'none') return;
    
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        autocompleteIndex = Math.min(autocompleteIndex + 1, filteredAgents.length - 1);
        updateAutocompleteSelection();
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        autocompleteIndex = Math.max(autocompleteIndex - 1, -1);
        updateAutocompleteSelection();
    } else if (e.key === 'Enter' && autocompleteIndex >= 0) {
        e.preventDefault();
        selectAgent(filteredAgents[autocompleteIndex].name);
    } else if (e.key === 'Escape') {
        hideAutocomplete();
    }
}

function updateAutocompleteSelection() {
    const items = elements.agentAutocomplete.querySelectorAll('.autocomplete-item');
    items.forEach((item, index) => {
        if (index === autocompleteIndex) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
}

function selectAgent(agentName) {
    const value = elements.messageInput.value;
    const cursorPos = elements.messageInput.selectionStart;
    const textBeforeCursor = value.substring(0, cursorPos);
    const textAfterCursor = value.substring(cursorPos);
    
    // 替换@mention
    const newTextBefore = textBeforeCursor.replace(/@([^\s]*)$/, `@${agentName} `);
    elements.messageInput.value = newTextBefore + textAfterCursor;
    elements.messageInput.setSelectionRange(newTextBefore.length, newTextBefore.length);
    elements.messageInput.focus();
    
    hideAutocomplete();
}

// ===== 停止/继续讨论 =====

async function stopDiscussion() {
    if (currentAbortController) {
        // 中断当前请求
        currentAbortController.abort();
        currentAbortController = null;
    }
    
    if (currentDiscussionId) {
        try {
            await fetch(`${API_BASE}/discussions/${currentDiscussionId}/pause`, {
                method: 'POST'
            });
            isPaused = true;
            elements.stopBtn.style.display = 'none';
            elements.resumeBtn.style.display = 'block';
        } catch (error) {
            console.error('暂停失败:', error);
        }
    }
}

async function resumeDiscussion() {
    if (!currentDiscussionId) return;
    
    try {
        await fetch(`${API_BASE}/discussions/${currentDiscussionId}/resume`, {
            method: 'POST'
        });
        isPaused = false;
        elements.stopBtn.style.display = 'none';
        elements.resumeBtn.style.display = 'none';
        
        // 继续讨论（从上次停止的地方）
        await streamDiscussion('continue', '');
    } catch (error) {
        console.error('继续失败:', error);
        showError('继续讨论失败');
    }
}

// ===== 数据增强 =====

async function triggerDataEnhancement() {
    if (!currentDiscussionId) return;
    
    try {
        // 获取所有消息
        const response = await fetch(`${API_BASE}/discussions/${currentDiscussionId}`);
        const data = await response.json();
        
        // 提取所有Agent消息中的股票代码
        const allText = data.messages
            .filter(msg => msg.message_type === 'agent')
            .map(msg => msg.content)
            .join(' ');
        
        const symbols = extractStockSymbols(allText);
        
        if (symbols.length > 0) {
            elements.enhanceBtn.disabled = true;
            elements.enhanceBtn.textContent = '📊 加载中...';
            await enhanceWithStockData(symbols);
            elements.enhanceBtn.disabled = false;
            elements.enhanceBtn.textContent = '📊 数据增强';
        } else {
            showError('未检测到股票代码，请确保讨论中包含股票名称或代码');
        }
    } catch (error) {
        console.error('数据增强失败:', error);
        showError('数据增强失败');
        elements.enhanceBtn.disabled = false;
        elements.enhanceBtn.textContent = '📊 数据增强';
    }
}

async function autoEnhanceWithData() {
    if (!currentDiscussionId) return;
    
    try {
        // 获取所有消息
        const response = await fetch(`${API_BASE}/discussions/${currentDiscussionId}`);
        const data = await response.json();
        
        // 提取所有Agent消息中的股票代码
        const allText = data.messages
            .filter(msg => msg.message_type === 'agent')
            .map(msg => msg.content)
            .join(' ');
        
        // 使用简单的正则提取股票代码
        const symbols = extractStockSymbols(allText);
        
        if (symbols.length > 0) {
            // 调用数据增强API
            await enhanceWithStockData(symbols);
        }
    } catch (error) {
        console.error('自动增强失败:', error);
    }
}

function extractStockSymbols(text) {
    // 扩展股票代码映射
    const stockMap = {
        "特斯拉": "TSLA", "苹果": "AAPL", "微软": "MSFT", "英伟达": "NVDA",
        "谷歌": "GOOGL", "亚马逊": "AMZN", "Meta": "META", "脸书": "META",
        "Netflix": "NFLX", "奈飞": "NFLX", "阿里巴巴": "BABA", "腾讯": "TCEHY",
        "比亚迪": "BYDDF", "蔚来": "NIO", "理想": "LI", "小鹏": "XPEV",
        "特斯拉": "TSLA", "苹果公司": "AAPL", "微软公司": "MSFT"
    };
    
    // 常见误识别词黑名单（扩展）
    const blacklist = new Set([
        "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "HER", "WAS", 
        "ONE", "OUR", "OUT", "DAY", "GET", "HAS", "HIM", "HIS", "HOW", "ITS", "MAY", 
        "NEW", "NOW", "OLD", "SEE", "TWO", "WAY", "WHO", "BOY", "DID", "LET", "PUT", 
        "SAY", "SHE", "TOO", "USE", "AI", "IT", "API", "CEO", "CFO", "CTO", "USA", 
        "UK", "EU", "USD", "CNY", "GDP", "CPI", "PMI", "ETF", "IPO", "SEC", "FDA"
    ]);
    
    // 常见股票代码白名单（美股主要股票）
    const whitelist = new Set([
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "NFLX", "BABA",
        "JPM", "V", "JNJ", "WMT", "PG", "MA", "UNH", "HD", "DIS", "PYPL", "BAC",
        "XOM", "VZ", "ADBE", "CMCSA", "NKE", "CSCO", "PFE", "MRK", "ABT", "TMO"
    ]);
    
    const symbols = [];
    const upperText = text.toUpperCase();
    
    // 提取美股代码（2-5个大写字母）
    const codePattern = /\b([A-Z]{2,5})\b/g;
    const matches = upperText.matchAll(codePattern);
    
    for (const match of matches) {
        const code = match[1];
        // 优先检查白名单，如果在白名单中直接添加
        if (whitelist.has(code)) {
            symbols.push(code);
        }
        // 否则检查是否在黑名单中，如果不在且长度>=2，可能是股票代码
        else if (!blacklist.has(code) && code.length >= 2 && code.length <= 5) {
            // 进一步验证：如果代码出现在常见股票上下文中（如"$AAPL"或"AAPL stock"）
            const context = text.substring(Math.max(0, match.index - 10), Math.min(text.length, match.index + code.length + 10));
            if (context.includes('$') || context.toLowerCase().includes('stock') || context.toLowerCase().includes('股价')) {
                symbols.push(code);
            }
        }
    }
    
    // 提取中文名称
    for (const [chinese, symbol] of Object.entries(stockMap)) {
        if (text.includes(chinese) && !symbols.includes(symbol)) {
            symbols.push(symbol);
        }
    }
    
    // 去重并限制数量
    return [...new Set(symbols)].slice(0, 10);
}

async function enhanceWithStockData(symbols) {
    if (!currentDiscussionId || symbols.length === 0) return;
    
    try {
        const response = await fetch(`${API_BASE}/discussions/${currentDiscussionId}/enhance-with-data`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbols })
        });
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let currentAgentId = null;
        let currentMessageDiv = null;
        let currentContentDiv = null;
        let currentRawContent = '';
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.type === 'data_loaded') {
                            const dataDiv = document.createElement('div');
                            dataDiv.className = 'debate-separator';
                            dataDiv.innerHTML = `<div class="debate-label">📊 已加载实时数据: ${data.symbols.join(', ')}</div>`;
                            elements.messagesContainer.appendChild(dataDiv);
                            scrollToBottom();
                        } else if (data.type === 'agent_start') {
                            currentAgentId = data.agent_id;
                            currentRawContent = '';
                            currentMessageDiv = appendAgentMessage(data.agent_name, data.agent_role + ' (数据验证)');
                            currentContentDiv = currentMessageDiv.querySelector('.message-content');
                            currentContentDiv.innerHTML = '<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>';
                        } else if (data.type === 'content' && currentContentDiv) {
                            const typingIndicator = currentContentDiv.querySelector('.typing-indicator');
                            if (typingIndicator) {
                                typingIndicator.remove();
                            }
                            currentRawContent += data.content;
                            currentContentDiv.innerHTML = renderMarkdown(currentRawContent);
                            scrollToBottom();
                        } else if (data.type === 'agent_end') {
                            currentAgentId = null;
                            currentContentDiv = null;
                            currentRawContent = '';
                        } else if (data.type === 'enhance_done') {
                            const doneDiv = document.createElement('div');
                            doneDiv.className = 'debate-separator';
                            doneDiv.innerHTML = '<div class="debate-label">✅ 数据增强分析完成</div>';
                            elements.messagesContainer.appendChild(doneDiv);
                            scrollToBottom();
                        }
                    } catch (e) {
                        console.error('解析SSE数据失败:', e);
                    }
                }
            }
        }
    } catch (error) {
        console.error('数据增强失败:', error);
    }
}

// 将函数暴露到全局作用域（供HTML onclick使用）
// 这些函数在文件前面已经定义，直接暴露即可
window.editAgent = editAgent;
window.deleteAgent = deleteAgent;
window.loadDefaultTeam = loadDefaultTeam;
window.quickChangeModel = quickChangeModel;
window.loadDiscussion = loadDiscussion;
window.selectAgent = selectAgent;

// 初始化应用（等待DOM加载完成）
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log('DOM加载完成，开始初始化...');
        init();
    });
} else {
    console.log('DOM已就绪，立即初始化...');
    // 延迟一点确保所有元素都已渲染
    setTimeout(init, 50);
}

