document.addEventListener('DOMContentLoaded', () => {
    fetchCampaigns();
    setInterval(fetchCampaigns, 5000); // Polling for updates

    const form = document.getElementById('campaign-form');
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const title = document.getElementById('campaign-title').value;
        const prompt = document.getElementById('campaign-prompt').value;
        const platforms = Array.from(document.querySelectorAll('input[name="platforms"]:checked')).map(cb => cb.value);

        if (platforms.length === 0) {
            alert("Select at least one platform.");
            return;
        }

        const btn = document.getElementById('submit-campaign');
        const statusEl = document.getElementById('trigger-status');
        
        btn.disabled = true;
        btn.textContent = "Initiating...";
        statusEl.textContent = "";

        try {
            const csrfToken = getCookie('csrftoken');
            const res = await fetch('/api/campaigns/create/', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken || ''
                },
                body: JSON.stringify({ title, prompt, platforms })
            });

            if (res.ok) {
                statusEl.textContent = "Workflow Enqueued Successfully!";
                statusEl.style.color = "var(--success)";
                form.reset();
                fetchCampaigns();
            } else {
                const data = await res.json();
                statusEl.textContent = `Error: ${JSON.stringify(data)}`;
                statusEl.style.color = "var(--danger)";
            }
        } catch (err) {
            statusEl.textContent = `Error: ${err.message}`;
            statusEl.style.color = "var(--danger)";
        } finally {
            btn.disabled = false;
            btn.textContent = "Execute Workflow Agent";
        }
    });

    document.getElementById('close-modal').addEventListener('click', closeModal);
});

let currentCampaignId = null;

async function fetchCampaigns() {
    try {
        const res = await fetch('/api/campaigns/');
        if (res.ok) {
            const data = await res.json();
            renderCampaigns(data.results || data);
        }
    } catch(e) {
        console.error("Fetch error:", e);
    }
}

function renderCampaigns(campaigns) {
    const list = document.getElementById('campaign-list');
    if (!campaigns || campaigns.length === 0) {
        list.innerHTML = "<p class='text-muted'>No active campaigns.</p>";
        return;
    }

    list.innerHTML = "";
    campaigns.forEach(c => {
        const card = document.createElement('div');
        card.className = 'campaign-card';
        
        let badgeClass = 'pending';
        if (c.status === 'RUNNING') badgeClass = 'running';
        if (c.status === 'AWAITING_APPROVAL') badgeClass = 'awaiting';
        if (c.status === 'PUBLISHED') badgeClass = 'published';
        if (c.status === 'FAILED') badgeClass = 'failed';

        let actionHtml = '';
        if (c.status === 'AWAITING_APPROVAL') {
            actionHtml = `<button onclick="openApprovalModal('${c.id}')" style="margin-top:0.5rem;font-size:0.8rem;padding:0.4rem;background:#8b5cf6;color:#fff;border:none;border-radius:4px;cursor:pointer;">Review Required (HITL)</button>`;
        }

        card.innerHTML = `
            <div class="campaign-header">
                <strong>${c.title}</strong>
                <span class="badge ${badgeClass}">${c.status}</span>
            </div>
            <div style="font-size:0.85rem;color:var(--text-muted);margin-bottom:0.5rem;">
                ${c.raw_prompt.length > 60 ? c.raw_prompt.substring(0, 60) + '...' : c.raw_prompt}
            </div>
            ${actionHtml}
        `;
        list.appendChild(card);
    });
}

async function openApprovalModal(id) {
    currentCampaignId = id;
    const modal = document.getElementById('approval-modal');
    const detailsWrap = document.getElementById('modal-campaign-details');
    detailsWrap.innerHTML = "<p>Loading draft data...</p>";
    modal.classList.remove('hidden');

    try {
        const res = await fetch(`/api/campaigns/${id}/`);
        const data = await res.json();
        
        let postsHtml = "";
        if (data.posts && data.posts.length > 0) {
            data.posts.forEach(p => {
                postsHtml += `
                    <h4 style="margin-bottom: 0.5rem; color: var(--accent);">${p.platform} draft</h4>
                    <div class="post-preview">${p.post_text}</div>
                `;
            });
        } else {
            postsHtml = "<p class='text-muted'>No drafts generated yet.</p>";
        }
        
        detailsWrap.innerHTML = `
            <p><strong>Avg Quality Score:</strong> ${(data.overall_quality_score) || 'N/A'}</p>
            <div style="margin-top:1rem; max-height: 40vh; overflow-y: auto;">
                ${postsHtml}
            </div>
            <label style="display:block;margin-top:1rem;font-size:0.9rem; color:var(--text-muted);">Reviewer Notes (Optional):</label>
            <textarea id="reviewer-notes" style="width:100%;padding:0.5rem;background:var(--bg-dark);color:var(--text);border:1px solid var(--border);border-radius:4px; margin-top: 0.5rem;" rows="2"></textarea>
        `;

        document.getElementById('btn-approve').onclick = () => submitApproval(id, true);
        document.getElementById('btn-reject').onclick = () => submitApproval(id, false);

    } catch (e) {
        detailsWrap.innerHTML = `<p style="color:var(--danger)">Error loading details.</p>`;
    }
}

function closeModal() {
    document.getElementById('approval-modal').classList.add('hidden');
    currentCampaignId = null;
}

async function submitApproval(id, isApproved) {
    const notes = document.getElementById('reviewer-notes').value;
    const csrfToken = getCookie('csrftoken');
    
    try {
        const res = await fetch(`/api/campaigns/${id}/approve/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken || ''
            },
            body: JSON.stringify({ approved: isApproved, notes: notes })
        });
        
        if (res.ok) {
            closeModal();
            fetchCampaigns();
        } else {
            alert("Error submitting decision.");
        }
    } catch(e) {
        console.error(e);
        alert("Request failed.");
    }
}

// Helpers
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
