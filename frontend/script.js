/**
 * Commons Depicts Analyzer - Frontend JavaScript
 */

const elements = {
    form: document.getElementById('analyze-form'),
    categoryInput: document.getElementById('category-input'),
    analyzeBtn: document.getElementById('analyze-btn'),
    suggestionsList: document.getElementById('suggestions-list'),

    // Sections
    historySection: document.getElementById('history-section'),
    historyGrid: document.getElementById('history-grid'),
    refreshHistoryBtn: document.getElementById('refresh-history-btn'),

    statusMessage: document.getElementById('status-message'),
    statisticsSection: document.getElementById('statistics-section'),
    resultsSection: document.getElementById('results-section'),

    // Stats
    statTotal: document.getElementById('stat-total'),
    statWithDepicts: document.getElementById('stat-with-depicts'),
    statWithoutDepicts: document.getElementById('stat-without-depicts'),
    statCoverage: document.getElementById('stat-coverage'),

    // Tables
    tableWithDepicts: document.getElementById('table-with-depicts'),
    tableWithoutDepicts: document.getElementById('table-without-depicts'),
    emptyWith: document.getElementById('empty-with'),
    emptyWithout: document.getElementById('empty-without'),
    countWith: document.getElementById('count-with'),
    countWithout: document.getElementById('count-without'),
};

// ============ State ============
let debounceTimer;

// ============ API Functions ============

async function analyzeCategory(category) {
    const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Analysis failed');
    return data;
}

async function fetchHistory() {
    try {
        const response = await fetch('/api/history');
        if (!response.ok) return [];
        return await response.json();
    } catch (e) {
        console.error("Failed to fetch history", e);
        return [];
    }
}

async function deleteHistoryItem(category) {
    await fetch('/api/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category })
    });
    loadHistory(); // Refresh
}

async function fetchSuggestions(query) {
    try {
        const response = await fetch(`/api/autocomplete?q=${encodeURIComponent(query)}`);
        if (!response.ok) return [];
        return await response.json();
    } catch (e) {
        return [];
    }
}

// ============ UI Functions ============

function renderHistory(historyItems) {
    if (!historyItems || historyItems.length === 0) {
        elements.historySection.classList.add('hidden');
        return;
    }

    elements.historySection.classList.remove('hidden');
    elements.historyGrid.innerHTML = '';

    historyItems.forEach(item => {
        const coverage = item.total > 0 ? Math.round((item.with_depicts / item.total) * 100) : 0;
        const colorClass = coverage >= 70 ? 'coverage-good' : (coverage >= 40 ? 'coverage-mid' : 'coverage-bad');
        const progressBarColor = coverage >= 70 ? 'var(--color-success)' : (coverage >= 40 ? 'var(--color-warning)' : 'var(--color-danger)');

        const card = document.createElement('div');
        card.className = 'history-card';
        card.innerHTML = `
            <div class="card-header">
                <div>
                    <h3 class="card-title" title="${escapeHtml(item.category)}">
                        <i class="fa-solid fa-folder"></i> ${escapeHtml(item.category.replace('Category:', ''))}
                    </h3>
                </div>
                <div class="coverage-badge ${colorClass}">${coverage}%</div>
            </div>
            
            <div class="progress-container">
                <div class="progress-bar" style="width: ${coverage}%; background-color: ${progressBarColor}"></div>
            </div>

            <div class="card-stats">
                <span><i class="fa-regular fa-file"></i> ${item.total} files</span>
                <span class="text-success"><i class="fa-solid fa-check"></i> ${item.with_depicts}</span>
                <span class="text-danger"><i class="fa-solid fa-xmark"></i> ${item.without_depicts}</span>
            </div>

            <div class="card-actions">
                <button class="btn btn-sm btn-outline re-analyze-btn">
                    <i class="fa-solid fa-rotate"></i> Re-scan
                </button>
                <button class="btn btn-sm btn-outline delete-btn" title="Delete results">
                    <i class="fa-solid fa-trash"></i>
                </button>
                <a href="${getCommonsUrl(item.category)}" target="_blank" class="btn btn-sm btn-outline">
                    <i class="fa-solid fa-arrow-up-right-from-square"></i> Commons
                </a>
            </div>
        `;

        // Bind events
        card.querySelector('.re-analyze-btn').addEventListener('click', () => {
            elements.categoryInput.value = item.category.replace('Category:', '');
            elements.form.dispatchEvent(new Event('submit'));
        });

        card.querySelector('.delete-btn').addEventListener('click', (e) => {
            if (confirm(`Delete analysis for "${item.category}"?`)) {
                deleteHistoryItem(item.category);
            }
        });

        elements.historyGrid.appendChild(card);
    });
}

async function loadHistory() {
    const history = await fetchHistory();
    renderHistory(history);
}

// ============ Autocomplete ============

elements.categoryInput.addEventListener('input', (e) => {
    const query = e.target.value.trim();
    clearTimeout(debounceTimer);

    if (query.length < 2) {
        elements.suggestionsList.classList.add('hidden');
        return;
    }

    debounceTimer = setTimeout(async () => {
        const suggestions = await fetchSuggestions(query);
        renderSuggestions(suggestions);
    }, 300);
});

function renderSuggestions(suggestions) {
    elements.suggestionsList.innerHTML = '';

    if (suggestions.length === 0) {
        elements.suggestionsList.classList.add('hidden');
        return;
    }

    suggestions.forEach(suggestion => {
        const li = document.createElement('li');
        li.className = 'suggestion-item';
        li.innerHTML = `<i class="fa-solid fa-magnifying-glass input-icon" style="position:static; margin-right:8px; font-size:0.8em"></i> ${escapeHtml(suggestion)}`;

        li.addEventListener('click', () => {
            elements.categoryInput.value = suggestion;
            elements.suggestionsList.classList.add('hidden');
            // Optional: Auto-submit? No, let user review.
        });

        elements.suggestionsList.appendChild(li);
    });

    elements.suggestionsList.classList.remove('hidden');
}

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
    if (!elements.categoryInput.contains(e.target) && !elements.suggestionsList.contains(e.target)) {
        elements.suggestionsList.classList.add('hidden');
    }
});

// ============ Main Handlers ============

async function handleSubmit(event) {
    event.preventDefault();
    const category = elements.categoryInput.value.trim();
    if (!category) return;

    setLoading(true);
    elements.suggestionsList.classList.add('hidden');
    showStatus(`Analyzing "${category}"...`, 'loading');

    elements.statisticsSection.classList.add('hidden');
    elements.resultsSection.classList.add('hidden');

    try {
        const result = await analyzeCategory(category);
        hideStatus();
        updateStatistics(result.statistics);
        populateTables(result.files);
        loadHistory(); // Refresh history after new analysis
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
    } finally {
        setLoading(false);
    }
}

// (Helpers like getCommonsUrl, escapeHtml, etc. assumed preserved or re-added)
// Re-adding essential helpers for completeness in this file rewrite context
function getCommonsUrl(title) {
    return `https://commons.wikimedia.org/wiki/${encodeURIComponent(title.replace(/ /g, '_'))}`;
}
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
function showStatus(msg, type) {
    elements.statusMessage.textContent = msg;
    elements.statusMessage.className = `status-message ${type}`;
    elements.statusMessage.classList.remove('hidden');
}
function hideStatus() { elements.statusMessage.classList.add('hidden'); }
function setLoading(isLoading) {
    elements.analyzeBtn.disabled = isLoading;
    elements.categoryInput.disabled = isLoading;
    elements.analyzeBtn.innerHTML = isLoading ? '<i class="fa-solid fa-spinner fa-spin"></i> Analyzing...' : '<i class="fa-solid fa-bolt"></i> Analyze';
}
function updateStatistics(stats) {
    elements.statTotal.textContent = stats.total;
    elements.statWithDepicts.textContent = stats.with_depicts;
    elements.statWithoutDepicts.textContent = stats.without_depicts;
    elements.statCoverage.textContent = stats.total > 0 ? Math.round((stats.with_depicts / stats.total) * 100) + '%' : '0%';
    elements.statisticsSection.classList.remove('hidden');
}
function populateTables(files) {
    const withDepicts = files.filter(f => f.has_depicts);
    const withoutDepicts = files.filter(f => !f.has_depicts);

    fillTable(elements.tableWithDepicts, withDepicts, 'with');
    fillTable(elements.tableWithoutDepicts, withoutDepicts, 'without');

    elements.resultsSection.classList.remove('hidden');
}
function fillTable(table, files, type) {
    const tbody = table.querySelector('tbody');
    tbody.innerHTML = '';
    const emptyMsg = document.getElementById(`empty-${type}`);
    const countBadge = document.getElementById(`count-${type}`);

    countBadge.textContent = files.length;

    if (files.length === 0) {
        table.classList.add('hidden');
        emptyMsg.classList.remove('hidden');
    } else {
        table.classList.remove('hidden');
        emptyMsg.classList.add('hidden');
        files.forEach((f, i) => {
            const tr = document.createElement('tr');
            if (type === 'with') {
                tr.innerHTML = `<td>${i + 1}</td><td><a href="${getCommonsUrl(f.file_name)}" target="_blank">${escapeHtml(f.file_name.replace('File:', ''))}</a></td><td>${escapeHtml(f.depicts)}</td>`;
            } else {
                tr.innerHTML = `<td>${i + 1}</td><td><a href="${getCommonsUrl(f.file_name)}" target="_blank">${escapeHtml(f.file_name.replace('File:', ''))}</a></td><td><a href="${getCommonsUrl(f.file_name)}#P180" target="_blank">+ Add</a></td>`;
            }
            tbody.appendChild(tr);
        });
    }
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    elements.form.addEventListener('submit', handleSubmit);
    elements.categoryInput.focus();
    loadHistory(); // Load initial history

    elements.refreshHistoryBtn.addEventListener('click', loadHistory);

    // Tab switching (simple version)
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
        });
    });
});
