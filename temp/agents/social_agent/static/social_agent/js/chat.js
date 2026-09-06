let currentSessionId = null;
let currentCampaignId = null; // Track latest campaign for telemetry

document.addEventListener('DOMContentLoaded', () => {
    initChat();
    loadModels();
    setInterval(pollUpdates, 5000);

    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const newSessionBtn = document.getElementById('new-session-btn');
    const toggleTelemetryBtn = document.getElementById('toggle-telemetry');
    const tempSlider = document.getElementById('temp-slider');
    const tempVal = document.getElementById('temp-val');

    tempSlider.addEventListener('input', (e) => {
        tempVal.innerText = e.target.value;
    });

    toggleTelemetryBtn.addEventListener('click', () => {
        document.getElementById('telemetry-drawer').classList.toggle('hidden');
    });

    newSessionBtn.addEventListener('click', async () => {
        await createSession();
    });

    chatInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        if (this.value === '') {
            this.style.height = 'auto';
        }
    });

    chatInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!currentSessionId) return;

        const prompt = chatInput.value.trim();
        if (!prompt) return;

        const agentRole = document.getElementById('agent-role').value;
        const modelSelect = document.getElementById('model-select').value;

        // Display locally first
        appendMessage('US', prompt, 'user-msg');
        chatInput.value = '';
        chatInput.style.height = 'auto';

        const typingId = addTypingIndicator();

        try {
            const csrfToken = getCookie('csrftoken');
            const res = await fetch(`/api/chat/sessions/${currentSessionId}/message/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken || ''
                },
                body: JSON.stringify({ content: prompt, agent_role: agentRole, model: modelSelect })
            });

            removeElement(typingId);

            if (res.ok) {
                const data = await res.json();
                const msg = data.message;
                appendMessage('AG', msg.content, 'agent-msg');
                if (msg.metadata && msg.metadata.campaign_id) {
                    trackedCampaigns.add(msg.metadata.campaign_id);
                    currentCampaignId = msg.metadata.campaign_id;
                    pollUpdates();
                }
            } else {
                const err = await res.json();
                appendMessage('AG', `Error: ${JSON.stringify(err)}`, 'agent-msg');
            }
        } catch (err) {
            removeElement(typingId);
            appendMessage('AG', `Network Error: ${err.message}`, 'agent-msg');
        }
    });
});

async function initChat() {
    await fetchSessions();
}

async function loadModels() {
    try {
        const res = await fetch('/api/models/');
        if (res.ok) {
            const data = await res.json();
            const select = document.getElementById('model-select');

            // Only clear and populate if we actually retrieved models dynamically
            if (data.models && data.models.length > 0) {
                select.innerHTML = '';
                data.models.forEach(model => {
                    const opt = document.createElement('option');
                    opt.value = model;
                    opt.textContent = model;
                    select.appendChild(opt);
                });
            }
        }
    } catch (e) {
        console.error("Failed to load models:", e);
    }
}

async function fetchSessions() {
    try {
        const res = await fetch('/api/chat/sessions/');
        if (res.ok) {
            const sessions = await res.json();
            renderSessions(sessions);
            if (sessions.length > 0 && !currentSessionId) {
                await loadSession(sessions[0].id, sessions[0].title);
            } else if (sessions.length === 0 && !currentSessionId) {
                await createSession();
            }
        }
    } catch (e) { console.error(e); }
}

function renderSessions(sessions) {
    const historyDiv = document.getElementById('session-history');
    historyDiv.innerHTML = '';
    sessions.forEach(s => {
        const div = document.createElement('div');
        div.className = 'history-item';
        div.title = s.title;
        div.textContent = s.title;
        if (s.id === currentSessionId) {
            div.style.backgroundColor = 'var(--msg-user)';
        }
        div.addEventListener('click', () => loadSession(s.id, s.title));
        historyDiv.appendChild(div);
    });
}

async function createSession() {
    const csrfToken = getCookie('csrftoken');
    const res = await fetch('/api/chat/sessions/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken || '' }
    });
    if (res.ok) {
        const data = await res.json();
        await fetchSessions();
        await loadSession(data.id, data.title);
    }
}

async function loadSession(id, title) {
    currentSessionId = id;
    document.getElementById('current-session-title').innerText = title;
    fetchSessions(); // Refresh active state

    // Clear chat
    document.getElementById('chat-messages').innerHTML = '';

    // Load messages
    try {
        const res = await fetch(`/api/chat/sessions/${id}/messages/`);
        if (res.ok) {
            const messages = await res.json();
            if (messages.length === 0) {
                appendMessage('AG', "Hello! I am your agentic Social Media Manager.\n\nAsk me for advice or Give me a campaign objective like 'launch a campaign for Next.js'.", 'agent-msg');
            } else {
                messages.forEach(m => {
                    appendMessage(m.role === 'user' ? 'US' : 'AG', m.content, m.role === 'user' ? 'user-msg' : 'agent-msg', m.metadata);
                });
            }
        }
    } catch (e) { console.error(e); }
}

const trackedCampaigns = new Set();
const renderedReviewMods = new Set();

async function pollUpdates() {
    if (trackedCampaigns.size > 0) {
        try {
            const res = await fetch('/api/campaigns/');
            if (res.ok) {
                const data = await res.json();
                const campaigns = data.results || data;
                await checkCampaignUpdates(campaigns);
            }
        } catch (e) { console.error(e); }
    }

    if (currentCampaignId && !document.getElementById('telemetry-drawer').classList.contains('hidden')) {
        updateTelemetry(currentCampaignId);
    }
}

async function updateTelemetry(campaignId) {
    try {
        const res = await fetch(`/api/campaigns/${campaignId}/audit/`);
        if (res.ok) {
            const data = await res.json();
            const logs = data.results || data;
            const container = document.getElementById('audit-steps');
            container.innerHTML = '';

            let totalTokens = 0;
            let totalLatency = 0;

            logs.forEach(log => {
                const div = document.createElement('div');
                div.className = 'audit-step';
                div.innerHTML = `<strong>${log.node_name}</strong> - ${log.agent_name}<br><span style="color:#888">${log.execution_time_seconds.toFixed(2)}s</span>`;
                container.appendChild(div);

                if (log.token_usage && log.token_usage.total_tokens) {
                    totalTokens += log.token_usage.total_tokens;
                }
                totalLatency += log.execution_time_seconds;
            });

            document.getElementById('tokens-consumed').innerText = totalTokens;
            document.getElementById('est-cost').innerText = '$' + ((totalTokens / 1000) * 0.002).toFixed(4);
            document.getElementById('avg-latency').innerText = logs.length > 0 ? (totalLatency / logs.length).toFixed(2) + 's' : '0s';
        }
    } catch (e) { }
}

async function checkCampaignUpdates(campaigns) {
    for (let c of campaigns) {
        if (trackedCampaigns.has(c.id) || c.status === 'AWAITING_APPROVAL') {
            if (c.status === 'AWAITING_APPROVAL' && !renderedReviewMods.has(c.id)) {
                renderedReviewMods.add(c.id);
                await renderHITLWidget(c.id);
            }
            if (c.status === 'PUBLISHED' && trackedCampaigns.has(c.id)) {
                appendMessage('AG', `✅ Workflow Complete! Campaign '${c.title}' has been successfully published across all configured platforms.`, 'agent-msg');
                trackedCampaigns.delete(c.id);
                renderedReviewMods.delete(c.id);
            }
            if (c.status === 'FAILED' && trackedCampaigns.has(c.id)) {
                appendMessage('AG', `🚨 Workflow Failed for campaign '${c.title}'. Check system logs.`, 'agent-msg');
                trackedCampaigns.delete(c.id);
            }
        }
    }
}

async function renderHITLWidget(campaignId) {
    try {
        const res = await fetch(`/api/campaigns/${campaignId}/`);
        const data = await res.json();

        let reviewHtml = `
            <div class="review-widget" id="widget-${campaignId}">
                <div class="widget-header">⚠️ Human-in-the-Loop Review Required</div>
                <div style="font-size:0.85rem; margin-bottom:1rem; color:var(--text-secondary);">
                    Audit Engine Avg Score: <strong>${data.overall_quality_score || 'N/A'}</strong><br>
                    Campaign ID: ${campaignId.slice(0, 8)}...
                </div>
        `;

        if (data.posts && data.posts.length > 0) {
            data.posts.forEach(p => {
                reviewHtml += `
                    <div class="platform-draft">
                        <h4>${p.platform}</h4>
                        <div>${escapeHtml(p.post_text)}</div>
                    </div>
                `;
            });
        }

        reviewHtml += `
                <textarea id="notes-${campaignId}" class="notes-box" placeholder="Optional reviewer instructions or modifications..." rows="2"></textarea>
                <div class="review-actions">
                    <button class="btn btn-reject" onclick="submitDecision('${campaignId}', false)">Reject & Halt</button>
                    <button class="btn btn-approve" onclick="submitDecision('${campaignId}', true)">Approve & Dispatch</button>
                </div>
            </div>
        `;

        appendRawMessage('AG', reviewHtml, 'agent-msg');

    } catch (e) {
        console.error(e);
    }
}

window.submitDecision = async function (campaignId, isApproved) {
    const notesEl = document.getElementById(`notes-${campaignId}`);
    const notes = notesEl ? notesEl.value : '';

    const widget = document.getElementById(`widget-${campaignId}`);
    if (widget) {
        const btns = widget.querySelectorAll('button');
        btns.forEach(b => b.disabled = true);
    }

    try {
        const csrfToken = getCookie('csrftoken');
        const res = await fetch(`/api/campaigns/${campaignId}/approve/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken || ''
            },
            body: JSON.stringify({ approved: isApproved, notes: notes })
        });

        if (res.ok) {
            appendMessage('US', isApproved ? "Proceed with dispatch." : "Halt the workflow, specifications unmet.", 'user-msg');
            setTimeout(() => {
                appendMessage('AG', isApproved ? "Received authorization. Dispatching via MCP..." : "Workflow aborted. Awaiting new instructions.", 'agent-msg');
            }, 500);
            if (widget) widget.style.opacity = '0.5';
        } else {
            alert("Error communicating with Control Plane.");
        }
    } catch (e) { console.error(e); }
};

function appendMessage(avatar, text, typeClass, metadata = null) {
    let msgHtml = `<div class="bubble">${escapeHtml(text)}</div>`;

    // Add special badges or cards if there's metadata
    if (metadata && metadata.intent === 'CAMPAIGN_TRIGGER') {
        msgHtml += `
            <div style="margin-top:0.5rem; display:flex; gap:0.5rem;">
               <span class="status-tag status-RUNNING">RUNNING</span>
               <span style="font-size:0.75rem; color:#888;">ID: ${metadata.campaign_id.slice(0, 8)}</span>
            </div>
        `;
        if (metadata.campaign_id) trackedCampaigns.add(metadata.campaign_id);
    }

    appendRawMessage(avatar, msgHtml, typeClass);
}

function appendRawMessage(avatar, htmlContent, typeClass) {
    const chatDiv = document.getElementById('chat-messages');

    const div = document.createElement('div');
    div.className = `message ${typeClass}`;

    let label = '';
    if (typeClass === 'agent-msg') {
        label = '<div style="font-size:0.8rem; color:var(--text-secondary); margin-bottom:0.5rem; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase;">Antigravity Agent</div>';
    } else {
        label = '<div style="font-size:0.8rem; color:var(--text-secondary); margin-bottom:0.5rem; text-align:right; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase;">You</div>';
    }

    div.innerHTML = `<div class="avatar">${avatar}</div><div style="flex:1; min-width:0;">${label}${htmlContent}</div>`;

    chatDiv.appendChild(div);
    chatDiv.scrollTop = chatDiv.scrollHeight;
}

function addTypingIndicator() {
    const id = 'typing-' + Date.now();
    const typingHtml = `
        <div class="bubble">
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    appendRawMessage('AG', typingHtml, 'agent-msg');
    const chatDiv = document.getElementById('chat-messages');
    chatDiv.lastElementChild.id = id;
    return id;
}

function removeElement(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function escapeHtml(unsafe) {
    return (unsafe || '')
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;")
        .replace(/\n/g, "<br>");
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
