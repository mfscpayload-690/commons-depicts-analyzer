/**
 * Commons Depicts Analyzer - Frontend JavaScript
 * 
 * Handles:
 * - Category analysis submission
 * - API communication with backend
 * - Dynamic table population
 * - Tab switching
 * - Loading/error states
 */

// ============ DOM Elements ============
const elements = {
    form: document.getElementById('analyze-form'),
    categoryInput: document.getElementById('category-input'),
    analyzeBtn: document.getElementById('analyze-btn'),
    statusMessage: document.getElementById('status-message'),
    statisticsSection: document.getElementById('statistics-section'),
    resultsSection: document.getElementById('results-section'),
    // Stats
    statTotal: document.getElementById('stat-total'),
    statWithDepicts: document.getElementById('stat-with-depicts'),
    statWithoutDepicts: document.getElementById('stat-without-depicts'),
    statCoverage: document.getElementById('stat-coverage'),
    // Suggestions + history
    suggestions: document.getElementById('suggestions'),
    historyWrap: document.getElementById('search-history'),
    historyChips: document.getElementById('history-chips'),
    historyClear: document.getElementById('history-clear'),
    // Tables
    tableWithDepicts: document.getElementById('table-with-depicts'),
    tableWithoutDepicts: document.getElementById('table-without-depicts'),
    emptyWith: document.getElementById('empty-with'),
    emptyWithout: document.getElementById('empty-without'),
    // Tabs
    countWith: document.getElementById('count-with'),
    countWithout: document.getElementById('count-without'),
};

const SEARCH_HISTORY_KEY = 'categorySearchHistory';
const SEARCH_HISTORY_LIMIT = 8;
const SUGGESTION_LIMIT = 8;
const SUGGESTION_DEBOUNCE_MS = 250;
const PAGE_SIZE = 50;

let suggestionItems = [];
let activeSuggestionIndex = -1;
let suggestionTimeout;
let activeJobId = null;
let coverageChart = null; // Chart.js instance
let currentLanguage = 'en'; // Default language
let currentCategory = ''; // Track current analyzed category
let pagedFiles = { with: [], without: [] };
let currentPages = { with: 1, without: 1 };
let suggestionAbortController = null;
let progressStats = {
    startTime: 0,
    lastTime: 0,
    lastProcessed: 0,
    emaRate: null
};

// ============ API Functions ============

/**
 * Analyze a Commons category
 * @param {string} category - Category name
 * @returns {Promise<Object>} Analysis results
 */
async function analyzeCategory(category) {
    const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ category }),
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || 'Analysis failed');
    }

    return data;
}

/**
 * Start a new analysis job
 */
async function startAnalysisJob(category) {
    const response = await fetch('/api/analyze?async=1&language=' + currentLanguage, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category })
    });

    if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to start analysis');
    }

    return await response.json();
}

/**
 * Fetch analysis progress
 * @param {string} jobId - Job ID
 * @returns {Promise<Object>} Progress info
 */
async function fetchProgress(jobId) {
    const response = await fetch(`/api/progress/${encodeURIComponent(jobId)}`);
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch progress');
    }

    return data;
}

/**
 * Fetch results for a category
 * @param {string} category - Category name
 * @returns {Promise<Object>} Analysis results
 */
async function fetchResults(category) {
    const response = await fetch(`/api/results/${encodeURIComponent(category)}`);
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch results');
    }

    return data;
}

/**
 * Fetch category suggestions
 * @param {string} query - Partial category name
 * @returns {Promise<Array>} Suggestions
 */
async function fetchSuggestions(query, options = {}) {
    const response = await fetch(`/api/suggest?query=${encodeURIComponent(query)}`, options);
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch suggestions');
    }

    return (data.suggestions || []).slice(0, SUGGESTION_LIMIT);
}

// ============ UI Functions ============

/**
 * Show status message
 * @param {string} message - Message to display
 * @param {string} type - 'loading', 'error', or 'success'
 */
function showStatus(message, type = 'loading') {
    elements.statusMessage.textContent = message;
    elements.statusMessage.className = `status-message ${type}`;
    elements.statusMessage.classList.remove('hidden');
}

/**
 * Hide status message
 */
function hideStatus() {
    elements.statusMessage.classList.add('hidden');
}

/**
 * Update statistics display
 * @param {Object} stats - Statistics object
 */
function updateStatistics(stats) {
    elements.statTotal.textContent = stats.total;
    elements.statWithDepicts.textContent = stats.with_depicts;
    elements.statWithoutDepicts.textContent = stats.without_depicts;

    const coverage = stats.total > 0
        ? Math.round((stats.with_depicts / stats.total) * 100)
        : 0;
    elements.statCoverage.textContent = `${coverage}%`;

    elements.statisticsSection.classList.remove('hidden');
}

/**
 * Normalize category input
 * @param {string} value - Raw input
 * @returns {string} Normalized category name
 */
function normalizeCategoryInput(value) {
    return value.replace(/^Category:/i, '').trim();
}

/**
 * Create Commons file URL from title
 * @param {string} fileTitle - File title (e.g., "File:Example.jpg")
 * @returns {string} Commons URL
 */
function getCommonsUrl(fileTitle) {
    const encodedTitle = encodeURIComponent(fileTitle.replace(/ /g, '_'));
    return `https://commons.wikimedia.org/wiki/${encodedTitle}`;
}

/**
 * Get thumbnail URL for a Commons file
 * @param {string} fileTitle - File title (e.g., "File:Example.jpg")
 * @param {number} width - Thumbnail width in pixels
 * @returns {string} Thumbnail URL
 */
function getThumbnailUrl(fileTitle, width = 60) {
    const fileName = fileTitle.replace('File:', '');
    return `https://commons.wikimedia.org/w/thumb.php?f=${encodeURIComponent(fileName)}&w=${width}`;
}

/**
 * Populate files table
 * @param {Array} files - Array of file objects
 */
function populateTables(files) {
    pagedFiles.with = files.filter(f => f.has_depicts);
    pagedFiles.without = files.filter(f => !f.has_depicts);

    currentPages.with = 1;
    currentPages.without = 1;

    // Update counts
    elements.countWith.textContent = pagedFiles.with.length;
    elements.countWithout.textContent = pagedFiles.without.length;

    renderTablePage('without');
    renderTablePage('with');

    elements.resultsSection.classList.remove('hidden');
}

function renderTablePage(type) {
    const files = type === 'with' ? pagedFiles.with : pagedFiles.without;
    const table = type === 'with' ? elements.tableWithDepicts : elements.tableWithoutDepicts;
    const empty = type === 'with' ? elements.emptyWith : elements.emptyWithout;
    const tbody = table.querySelector('tbody');

    tbody.innerHTML = '';

    if (files.length === 0) {
        table.classList.add('hidden');
        empty.classList.remove('hidden');
        updatePaginationControls(type, 0, 1);
        return;
    }

    table.classList.remove('hidden');
    empty.classList.add('hidden');

    const totalPages = Math.max(1, Math.ceil(files.length / PAGE_SIZE));
    const page = Math.min(currentPages[type], totalPages);
    currentPages[type] = page;

    const start = (page - 1) * PAGE_SIZE;
    const slice = files.slice(start, start + PAGE_SIZE);

    slice.forEach((file, index) => {
        const row = document.createElement('tr');
        const rowNumber = start + index + 1;

        if (type === 'without') {
            row.innerHTML = `
                <td>${rowNumber}</td>
                <td class="thumbnail-cell">
                    <img src="${getThumbnailUrl(file.file_name)}" 
                         alt="${escapeHtml(file.file_name.replace('File:', ''))}"
                         class="file-thumbnail"
                         loading="lazy"
                         onclick="showFilePreview('${escapeHtml(file.file_name)}')"
                         onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2260%22 height=%2260%22><rect fill=%22%23eee%22 width=%2260%22 height=%2260%22/><text x=%2230%22 y=%2234%22 text-anchor=%22middle%22 fill=%22%23999%22 font-size=%2210%22>No preview</text></svg>'">
                </td>
                <td class="file-link">
                    <a href="javascript:void(0)" onclick="showFilePreview('${escapeHtml(file.file_name)}')"
                       title="Click to preview">
                        ${escapeHtml(file.file_name.replace('File:', ''))}
                    </a>
                </td>
                <td>
                    <button type="button" class="btn btn-secondary" onclick="showFilePreview('${escapeHtml(file.file_name)}')"
                       title="Add depicts in app">
                        + Add depicts
                    </button>
                </td>
            `;
        } else {
            row.innerHTML = `
                <td>${rowNumber}</td>
                <td class="thumbnail-cell">
                    <img src="${getThumbnailUrl(file.file_name)}" 
                         alt="${escapeHtml(file.file_name.replace('File:', ''))}"
                         class="file-thumbnail"
                         loading="lazy"
                         onclick="showFilePreview('${escapeHtml(file.file_name)}')"
                         onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2260%22 height=%2260%22><rect fill=%22%23eee%22 width=%2260%22 height=%2260%22/><text x=%2230%22 y=%2234%22 text-anchor=%22middle%22 fill=%22%23999%22 font-size=%2210%22>No preview</text></svg>'">
                </td>
                <td class="file-link">
                    <a href="javascript:void(0)" onclick="showFilePreview('${escapeHtml(file.file_name)}')"
                       title="Click to preview">
                        ${escapeHtml(file.file_name.replace('File:', ''))}
                    </a>
                </td>
                <td class="depicts-cell">${escapeHtml(file.depicts || '')}</td>
            `;
        }

        tbody.appendChild(row);
    });

    updatePaginationControls(type, files.length, totalPages);
}

function updatePaginationControls(type, totalItems, totalPages) {
    const pagination = document.getElementById(`pagination-${type}`);
    const prevBtn = document.getElementById(`page-prev-${type}`);
    const nextBtn = document.getElementById(`page-next-${type}`);
    const info = document.getElementById(`page-info-${type}`);

    if (!pagination || !prevBtn || !nextBtn || !info) return;

    if (totalItems <= PAGE_SIZE) {
        pagination.classList.add('hidden');
        return;
    }

    pagination.classList.remove('hidden');
    info.textContent = `Page ${currentPages[type]} of ${totalPages}`;
    prevBtn.disabled = currentPages[type] <= 1;
    nextBtn.disabled = currentPages[type] >= totalPages;
}

function initPaginationControls() {
    const prevWithout = document.getElementById('page-prev-without');
    const nextWithout = document.getElementById('page-next-without');
    const prevWith = document.getElementById('page-prev-with');
    const nextWith = document.getElementById('page-next-with');

    if (prevWithout) {
        prevWithout.addEventListener('click', () => {
            currentPages.without = Math.max(1, currentPages.without - 1);
            renderTablePage('without');
        });
    }

    if (nextWithout) {
        nextWithout.addEventListener('click', () => {
            currentPages.without += 1;
            renderTablePage('without');
        });
    }

    if (prevWith) {
        prevWith.addEventListener('click', () => {
            currentPages.with = Math.max(1, currentPages.with - 1);
            renderTablePage('with');
        });
    }

    if (nextWith) {
        nextWith.addEventListener('click', () => {
            currentPages.with += 1;
            renderTablePage('with');
        });
    }
}

/**
 * Escape HTML special characters
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Set loading state
 * @param {boolean} isLoading - Whether loading
 */
function setLoading(isLoading) {
    elements.categoryInput.disabled = isLoading;
    if (isLoading) {
        elements.analyzeBtn.innerHTML = '<i class="fa-solid fa-stop"></i> Stop';
        elements.analyzeBtn.classList.add('btn-stop');
        elements.analyzeBtn.disabled = false;
        elements.analyzeBtn.onclick = (e) => { e.preventDefault(); cancelAnalysis(); };
    } else {
        elements.analyzeBtn.innerHTML = '<i class="fa-solid fa-bolt"></i> Analyze';
        elements.analyzeBtn.classList.remove('btn-stop');
        elements.analyzeBtn.disabled = false;
        elements.analyzeBtn.onclick = null;
    }
}

/**
 * Show toast notification
 * @param {string} message - Message to display
 * @param {string} type - Type: 'success', 'error', 'info', 'warning'
 * @param {number} duration - Duration in ms (default: 4000)
 */
function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const iconMap = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        info: 'fa-info-circle',
        warning: 'fa-exclamation-triangle'
    };

    toast.innerHTML = `
        <i class="fa-solid ${iconMap[type] || iconMap.info}"></i>
        <span class="toast-message">${escapeHtml(message)}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">
            <i class="fa-solid fa-times"></i>
        </button>
    `;

    container.appendChild(toast);

    // Auto-dismiss
    setTimeout(() => {
        toast.classList.add('toast-fade-out');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/**
 * Render doughnut chart for coverage visualization
 * @param {Object} stats - Statistics object
 */
function renderCoverageChart(stats) {
    const canvas = document.getElementById('coverage-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');

    // Destroy previous chart
    if (coverageChart) {
        coverageChart.destroy();
    }

    // Theme-aware colors
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const textColor = isDark ? '#e3e3e3' : '#202122';
    const gridColor = isDark ? '#3a3f44' : '#c8ccd1';

    coverageChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['With Depicts (P180)', 'Without Depicts'],
            datasets: [{
                data: [stats.with_depicts, stats.without_depicts],
                backgroundColor: [
                    'rgba(20, 134, 109, 0.8)',  // Success color
                    'rgba(172, 102, 0, 0.8)'     // Warning color
                ],
                borderColor: [
                    'rgba(20, 134, 109, 1)',
                    'rgba(172, 102, 0, 1)'
                ],
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: textColor,
                        padding: 15,
                        font: {
                            size: 13
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = stats.total;
                            const percent = ((value / total) * 100).toFixed(1);
                            return `${label}: ${value} (${percent}%)`;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Download export in specified format
 * @param {string} format - 'csv' or 'json'
 */
function downloadExport(format) {
    if (!currentCategory) {
        showToast('No category to export', 'warning');
        return;
    }

    const url = `/api/export/${encodeURIComponent(currentCategory)}?format=${format}`;

    // Create temporary link and trigger download
    const link = document.createElement('a');
    link.href = url;
    link.download = '';  // Filename from Content-Disposition header
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    showToast(`Downloading ${format.toUpperCase()} export...`, 'success', 2000);
}

// Make downloadExport globally accessible
window.downloadExport = downloadExport;

function showProgress(percentValue, labelText, detailText) {
    const progress = document.getElementById('progress');
    const bar = document.getElementById('progress-bar');
    const percent = document.getElementById('progress-percent');
    const label = document.getElementById('progress-label');
    const detail = document.getElementById('progress-detail');

    if (!progress || !bar || !percent || !label || !detail) return;

    const safePercent = Math.max(0, Math.min(100, Math.round(percentValue)));
    label.textContent = labelText || 'Analyzing category';
    detail.textContent = detailText || '';
    percent.textContent = `${safePercent}%`;
    bar.style.width = `${safePercent}%`;

    progress.classList.remove('hidden');
}

function resetProgressStats() {
    progressStats = {
        startTime: 0,
        lastTime: 0,
        lastProcessed: 0,
        emaRate: null
    };
}

function formatDuration(seconds) {
    if (!isFinite(seconds) || seconds <= 0) return '';
    const total = Math.round(seconds);
    const hrs = Math.floor(total / 3600);
    const mins = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    if (hrs > 0) {
        return `${hrs}h ${String(mins).padStart(2, '0')}m`;
    }
    return `${mins}m ${String(secs).padStart(2, '0')}s`;
}

function completeProgress() {
    showProgress(100, 'Completed', 'Done — results are ready');
    setTimeout(() => {
        const progress = document.getElementById('progress');
        if (progress) progress.classList.add('hidden');
    }, 1200);
}

function hideProgress() {
    const progress = document.getElementById('progress');
    if (progress) progress.classList.add('hidden');
}

function updateProgressFromStatus(status) {
    const category = status.category || '';
    const catDisplay = category.replace(/^Category:/i, '');

    const phaseLabels = {
        queued: `Analyzing "${catDisplay}"`,
        fetching: `Analyzing "${catDisplay}" — fetching files`,
        checking: `Analyzing "${catDisplay}"`,
        finalizing: `Analyzing "${catDisplay}" — finalizing`,
        done: 'Completed',
        error: 'Error'
    };

    const label = phaseLabels[status.phase] || `Analyzing "${catDisplay}"`;
    let detail = status.message || '';

    if (status.total) {
        const processed = status.processed || 0;
        const total = status.total;
        const now = Date.now();

        if (!progressStats.startTime) {
            progressStats.startTime = now;
            progressStats.lastTime = now;
            progressStats.lastProcessed = processed;
        } else if (processed > progressStats.lastProcessed) {
            const deltaTime = (now - progressStats.lastTime) / 1000;
            const deltaProcessed = processed - progressStats.lastProcessed;
            if (deltaTime > 0 && deltaProcessed > 0) {
                const rate = deltaProcessed / deltaTime;
                progressStats.emaRate = progressStats.emaRate == null
                    ? rate
                    : (0.3 * rate + 0.7 * progressStats.emaRate);
            }
            progressStats.lastTime = now;
            progressStats.lastProcessed = processed;
        }

        let etaText = '';
        if (progressStats.emaRate && progressStats.emaRate > 0) {
            const remaining = Math.max(0, total - processed);
            etaText = formatDuration(remaining / progressStats.emaRate);
        }

        detail = `Processed ${processed} of ${total} files`;
        if (etaText) {
            detail += ` • ETA ${etaText}`;
        }
    }

    showProgress(status.percent || 0, label, detail);
}

async function pollProgress(jobId, category) {
    while (jobId === activeJobId) {
        const status = await fetchProgress(jobId);
        updateProgressFromStatus(status);

        if (status.status === 'done') {
            return fetchResults(category);
        }

        if (status.status === 'error') {
            throw new Error(status.error || 'Analysis failed');
        }

        if (status.status === 'cancelled') {
            throw new Error('Analysis canceled');
        }

        await new Promise((resolve) => setTimeout(resolve, 800));
    }

    throw new Error('Analysis canceled');
}

// ============ Suggestions + History ============

function getSearchHistory() {
    const stored = localStorage.getItem(SEARCH_HISTORY_KEY);
    if (!stored) return [];
    try {
        const parsed = JSON.parse(stored);
        return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
        return [];
    }
}

function renderSearchHistory(history) {
    if (!elements.historyWrap || !elements.historyChips) return;

    elements.historyChips.innerHTML = '';

    if (!history || history.length === 0) {
        elements.historyWrap.classList.add('hidden');
        return;
    }

    history.forEach((name) => {
        const chip = document.createElement('div');
        chip.className = 'history-chip';

        const label = document.createElement('span');
        label.textContent = name;
        label.addEventListener('click', () => {
            elements.categoryInput.value = name;
            elements.form.dispatchEvent(new Event('submit'));
        });

        const removeBtn = document.createElement('span');
        removeBtn.className = 'history-chip-remove';
        removeBtn.innerHTML = '<i class="fa-solid fa-times"></i>';
        removeBtn.title = 'Remove from history';
        removeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            removeSearchHistoryItem(name);
        });

        chip.appendChild(label);
        chip.appendChild(removeBtn);
        elements.historyChips.appendChild(chip);
    });

    elements.historyWrap.classList.remove('hidden');
}

function loadSearchHistory() {
    renderSearchHistory(getSearchHistory());
}

function saveSearchHistory(category) {
    const name = normalizeCategoryInput(category);
    if (!name) return;

    const history = getSearchHistory();
    const next = [name, ...history.filter((item) => item.toLowerCase() !== name.toLowerCase())];
    const trimmed = next.slice(0, SEARCH_HISTORY_LIMIT);

    localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(trimmed));
    renderSearchHistory(trimmed);
}

function removeSearchHistoryItem(name) {
    const history = getSearchHistory();
    const filtered = history.filter((item) => item !== name);
    localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(filtered));
    renderSearchHistory(filtered);

    // Show toast for feedback
    if (typeof showToast === 'function') {
        showToast('Removed from history', 'info', 2000);
    }
}

function clearSearchHistory() {
    localStorage.removeItem(SEARCH_HISTORY_KEY);
    renderSearchHistory([]);
    if (typeof showToast === 'function') {
        showToast('Search history cleared', 'info', 2000);
    }
}

function hideSuggestions() {
    if (!elements.suggestions) return;
    elements.suggestions.classList.add('hidden');
    elements.suggestions.innerHTML = '';
    suggestionItems = [];
    activeSuggestionIndex = -1;
}

function renderSuggestions(items) {
    if (!elements.suggestions) return;

    elements.suggestions.innerHTML = '';
    suggestionItems = items || [];
    activeSuggestionIndex = -1;

    if (!items || items.length === 0) {
        //        renderSuggestionsEmpty();
        return;
    }

    const header = document.createElement('div');
    header.className = 'suggestions-header';
    header.textContent = 'Suggested categories';
    elements.suggestions.appendChild(header);

    items.forEach((item, index) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'suggestion-item';
        button.setAttribute('role', 'option');
        button.dataset.index = String(index);
        button.innerHTML = `
            <span class="suggestion-icon"><i class="fa-solid fa-folder"></i></span>
            <span class="suggestion-prefix">Category</span>
            <span class="suggestion-text">${escapeHtml(item)}</span>
        `;
        button.addEventListener('mousedown', (event) => {
            event.preventDefault();
            selectSuggestion(item);
        });
        elements.suggestions.appendChild(button);
    });

    const hint = document.createElement('div');
    hint.className = 'suggestions-hint';
    hint.innerHTML = '<i class="fa-solid fa-keyboard"></i> Use ↑/↓ to navigate, Enter to select';
    elements.suggestions.appendChild(hint);

    elements.suggestions.classList.remove('hidden');
}

function renderSuggestionsEmpty() {
    if (!elements.suggestions) return;

    elements.suggestions.innerHTML = '';
    suggestionItems = [];
    activeSuggestionIndex = -1;

    const header = document.createElement('div');
    header.className = 'suggestions-header';
    header.textContent = 'Suggested categories';
    elements.suggestions.appendChild(header);

    const empty = document.createElement('div');
    empty.className = 'suggestions-empty';
    empty.innerHTML = '<i class="fa-solid fa-circle-info"></i> No matches found';
    elements.suggestions.appendChild(empty);

    const hint = document.createElement('div');
    hint.className = 'suggestions-hint';
    hint.innerHTML = '<i class="fa-solid fa-keyboard"></i> Use ↑/↓ to navigate, Enter to select';
    elements.suggestions.appendChild(hint);

    elements.suggestions.classList.remove('hidden');
}

function setActiveSuggestion(index) {
    if (!elements.suggestions) return;

    const items = Array.from(elements.suggestions.querySelectorAll('.suggestion-item'));
    if (items.length === 0) return;

    activeSuggestionIndex = (index + items.length) % items.length;
    items.forEach((item, i) => {
        item.classList.toggle('active', i === activeSuggestionIndex);
    });

    const active = items[activeSuggestionIndex];
    if (active) {
        active.scrollIntoView({ block: 'nearest' });
    }
}

function selectSuggestion(value) {
    elements.categoryInput.value = value;
    hideSuggestions();
    elements.categoryInput.focus();
}

function initSuggestions() {
    if (!elements.categoryInput || !elements.suggestions) return;

    elements.categoryInput.addEventListener('input', () => {
        const query = normalizeCategoryInput(elements.categoryInput.value);
        if (query.length < 2) {
            hideSuggestions();
            return;
        }

        clearTimeout(suggestionTimeout);
        suggestionTimeout = setTimeout(async () => {
            try {
                const items = await fetchSuggestions(query);
                renderSuggestions(items);
            } catch (error) {
                hideSuggestions();
            }
        }, SUGGESTION_DEBOUNCE_MS);
    });

    elements.categoryInput.addEventListener('keydown', (event) => {
        if (!elements.suggestions || elements.suggestions.classList.contains('hidden')) return;

        if (event.key === 'ArrowDown') {
            event.preventDefault();
            setActiveSuggestion(activeSuggestionIndex + 1);
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            setActiveSuggestion(activeSuggestionIndex - 1);
        } else if (event.key === 'Enter' && activeSuggestionIndex >= 0) {
            event.preventDefault();
            selectSuggestion(suggestionItems[activeSuggestionIndex]);
        } else if (event.key === 'Escape') {
            hideSuggestions();
        }
    });

    document.addEventListener('click', (event) => {
        const wrapper = elements.categoryInput?.parentElement;
        if (wrapper && !wrapper.contains(event.target)) {
            hideSuggestions();
        }
    });
}

// ============ Tab Handling ============

function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.dataset.tab;

            // Update buttons
            tabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');

            // Update content
            tabContents.forEach(content => {
                content.classList.remove('active');
                if (content.id === `tab-${tabId}`) {
                    content.classList.add('active');
                }
            });
        });
    });
}

// ============ Event Handlers ============

async function cancelAnalysis() {
    if (!activeJobId) return;
    try {
        await fetch(`/api/cancel/${encodeURIComponent(activeJobId)}`, { method: 'POST' });
    } catch (_) { /* ignore */ }
    activeJobId = null;
    hideProgress();
    setLoading(false);
    showStatus('Analysis stopped.', 'error');
    setTimeout(hideStatus, 2500);
}

async function handleSubmit(event) {
    event.preventDefault();

    const category = elements.categoryInput.value.trim();
    if (!category) {
        showToast('Please enter a category name', 'error');
        return;
    }

    currentCategory = category; // Track for exports
    setLoading(true);
    hideStatus();
    showProgress(4, `Analyzing "${category}"`, 'Preparing analysis');

    // Hide previous results
    elements.statisticsSection.classList.add('hidden');
    elements.resultsSection.classList.add('hidden');

    try {
        const job = await startAnalysisJob(category);
        activeJobId = job.job_id;
        const result = await pollProgress(activeJobId, category);

        currentCategory = result.category; // Store full category name

        updateStatistics(result.statistics);
        populateTables(result.files);
        renderCoverageChart(result.statistics); // Render chart
        saveSearchHistory(category);

        showToast(`Analysis complete! Found ${result.statistics.total} files.`, 'success', 3000);
        completeProgress();

    } catch (error) {
        if (error.message === 'Analysis canceled') return;
        showToast(`Error: ${error.message}`, 'error');
        hideProgress();
    } finally {
        setLoading(false);
    }
}

// ============ Initialization ============

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initPaginationControls();
    elements.form.addEventListener('submit', handleSubmit);

    // Focus input on load
    elements.categoryInput.focus();

    // Load history on page load
    loadHistory();

    // Load search history on page load
    loadSearchHistory();

    // Refresh history button
    const refreshBtn = document.getElementById('refresh-history-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadHistory);
    }

    if (elements.historyClear) {
        elements.historyClear.addEventListener('click', clearSearchHistory);
    }

    initSuggestions();

    // Initialize appearance panel
    initAppearancePanel();
});

// ============ Appearance Panel ============

function initAppearancePanel() {
    const toggleBtn = document.getElementById('appearance-toggle');
    const closeBtn = document.getElementById('appearance-close');
    const panel = document.getElementById('appearance-panel');

    if (!toggleBtn || !panel) return;

    // Toggle panel visibility
    toggleBtn.addEventListener('click', () => {
        panel.classList.toggle('hidden');
    });

    // Close panel
    closeBtn.addEventListener('click', () => {
        panel.classList.add('hidden');
    });

    // Close on click outside
    document.addEventListener('click', (e) => {
        if (!panel.contains(e.target) && !toggleBtn.contains(e.target)) {
            panel.classList.add('hidden');
        }
    });

    // Load saved preferences
    loadAppearanceSettings();

    // Handle text size changes
    document.querySelectorAll('input[name="text-size"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            const size = e.target.value;
            if (size === 'standard') {
                document.documentElement.removeAttribute('data-text-size');
            } else {
                document.documentElement.setAttribute('data-text-size', size);
            }
            localStorage.setItem('textSize', size);
        });
    });

    // Handle width changes
    document.querySelectorAll('input[name="width"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            const width = e.target.value;
            if (width === 'standard') {
                document.documentElement.removeAttribute('data-width');
            } else {
                document.documentElement.setAttribute('data-width', width);
            }
            localStorage.setItem('width', width);
        });
    });

    // Handle color/theme changes
    document.querySelectorAll('input[name="color"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            const theme = e.target.value;
            applyTheme(theme);
            localStorage.setItem('theme', theme);

            // Re-render chart with new theme colors
            if (coverageChart && currentCategory) {
                const stats = {
                    total: parseInt(document.getElementById('stat-total').textContent) || 0,
                    with_depicts: parseInt(document.getElementById('stat-with-depicts').textContent) || 0,
                    without_depicts: parseInt(document.getElementById('stat-without-depicts').textContent) || 0
                };
                renderCoverageChart(stats);
            }
        });
    });

    // Handle language changes
    const languageSelect = document.getElementById('language-select');
    if (languageSelect) {
        // Load saved language
        currentLanguage = localStorage.getItem('language') || 'en';
        languageSelect.value = currentLanguage;

        languageSelect.addEventListener('change', (e) => {
            currentLanguage = e.target.value;
            localStorage.setItem('language', currentLanguage);
            showToast(`Language changed to ${e.target.selectedOptions[0].text}`, 'info', 2000);
        });
    }
}

function applyTheme(theme) {
    if (theme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
    } else if (theme === 'automatic') {
        // Check system preference
        if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
            document.documentElement.setAttribute('data-theme', 'dark');
        } else {
            document.documentElement.removeAttribute('data-theme');
        }
    } else {
        document.documentElement.removeAttribute('data-theme');
    }
}

function loadAppearanceSettings() {
    // Load text size
    const savedTextSize = localStorage.getItem('textSize') || 'standard';
    const textRadio = document.querySelector(`input[name="text-size"][value="${savedTextSize}"]`);
    if (textRadio) {
        textRadio.checked = true;
        if (savedTextSize !== 'standard') {
            document.documentElement.setAttribute('data-text-size', savedTextSize);
        }
    }

    // Load width
    const savedWidth = localStorage.getItem('width') || 'standard';
    const widthRadio = document.querySelector(`input[name="width"][value="${savedWidth}"]`);
    if (widthRadio) {
        widthRadio.checked = true;
        if (savedWidth !== 'standard') {
            document.documentElement.setAttribute('data-width', savedWidth);
        }
    }

    // Load theme
    const savedTheme = localStorage.getItem('theme') || 'light';
    const themeRadio = document.querySelector(`input[name="color"][value="${savedTheme}"]`);
    if (themeRadio) {
        themeRadio.checked = true;
        applyTheme(savedTheme);
    }
}

// ============ History Dashboard ============

/**
 * Fetch history from API
 */
async function fetchHistory() {
    const response = await fetch('/api/history');
    const data = await response.json();
    return data;
}

/**
 * Get coverage level class
 */
function getCoverageLevel(coverage) {
    if (coverage < 30) return 'low';
    if (coverage < 70) return 'medium';
    return 'high';
}

/**
 * Create a history card element
 */
function createHistoryCard(category) {
    const totalFiles = category.total_files || 0;
    const withDepicts = category.with_depicts || 0;
    const withoutDepicts = totalFiles - withDepicts;
    const coverage = totalFiles > 0 ? Math.round((withDepicts / totalFiles) * 100) : 0;
    const coverageLevel = getCoverageLevel(coverage);

    // Format category name (remove "Category:" prefix for display)
    const displayName = category.category.replace('Category:', '');

    const card = document.createElement('div');
    card.className = 'history-card';
    card.innerHTML = `
        <div class="history-card-header">
            <h3 class="history-card-title">
                <i class="fa-solid fa-folder"></i>
                ${escapeHtml(displayName)}
            </h3>
            <span class="history-card-coverage ${coverageLevel}">${coverage}%</span>
        </div>
        
        <div class="coverage-bar-container">
            <div class="coverage-bar ${coverageLevel}" style="width: ${coverage}%"></div>
        </div>
        
        <div class="history-card-stats">
            <span class="history-card-stat">
                <i class="fa-solid fa-images"></i> ${totalFiles} files
            </span>
            <span class="history-card-stat stat-with">
                <i class="fa-solid fa-check"></i> ${withDepicts} with P180
            </span>
            <span class="history-card-stat stat-without">
                <i class="fa-solid fa-xmark"></i> ${withoutDepicts} without
            </span>
        </div>
        
        <div class="history-card-actions">
            <a href="https://commons.wikimedia.org/wiki/${encodeURIComponent(category.category)}" 
               target="_blank" rel="noopener" class="history-card-action" title="View on Commons">
                <i class="fa-solid fa-external-link"></i> Commons
            </a>
            <button class="history-card-action" onclick="reanalyzeCategory('${escapeHtml(displayName)}')" title="Re-analyze">
                <i class="fa-solid fa-arrows-rotate"></i> Re-analyze
            </button>
            <button class="history-card-action danger" onclick="deleteCategory('${escapeHtml(displayName)}')" title="Delete from database">
                <i class="fa-solid fa-trash"></i> Delete
            </button>
        </div>
    `;

    return card;
}

/**
 * Re-analyze a category
 */
function reanalyzeCategory(categoryName) {
    elements.categoryInput.value = categoryName;
    elements.form.dispatchEvent(new Event('submit'));
}

/**
 * Update history summary stats
 */
function updateHistorySummary(categories) {
    const totalFiles = categories.reduce((sum, c) => sum + (c.total_files || 0), 0);
    const totalWithDepicts = categories.reduce((sum, c) => sum + (c.with_depicts || 0), 0);
    const avgCoverage = totalFiles > 0 ? Math.round((totalWithDepicts / totalFiles) * 100) : 0;

    document.getElementById('history-total-files').textContent = totalFiles;
    document.getElementById('history-total-categories').textContent = categories.length;
    document.getElementById('history-avg-coverage').textContent = avgCoverage + '%';
}

// Store history data for filtering/sorting
let historyData = [];

/**
 * Get coverage percentage for a category
 */
function getCoveragePercent(category) {
    const totalFiles = category.total_files || 0;
    const withDepicts = category.with_depicts || 0;
    return totalFiles > 0 ? Math.round((withDepicts / totalFiles) * 100) : 0;
}

/**
 * Sort history data
 */
function sortHistoryData(data, sortBy) {
    const sorted = [...data];
    switch (sortBy) {
        case 'name-asc':
            sorted.sort((a, b) => a.category.localeCompare(b.category));
            break;
        case 'name-desc':
            sorted.sort((a, b) => b.category.localeCompare(a.category));
            break;
        case 'coverage-desc':
            sorted.sort((a, b) => getCoveragePercent(b) - getCoveragePercent(a));
            break;
        case 'coverage-asc':
            sorted.sort((a, b) => getCoveragePercent(a) - getCoveragePercent(b));
            break;
        case 'files-desc':
            sorted.sort((a, b) => (b.total_files || 0) - (a.total_files || 0));
            break;
        case 'files-asc':
            sorted.sort((a, b) => (a.total_files || 0) - (b.total_files || 0));
            break;
        case 'recent-desc':
            // Newest first (most recent timestamp)
            sorted.sort((a, b) => {
                const timeA = new Date(a.last_analyzed || 0).getTime();
                const timeB = new Date(b.last_analyzed || 0).getTime();
                return timeB - timeA;
            });
            break;
        case 'recent-asc':
            // Oldest first (least recent timestamp)
            sorted.sort((a, b) => {
                const timeA = new Date(a.last_analyzed || 0).getTime();
                const timeB = new Date(b.last_analyzed || 0).getTime();
                return timeA - timeB;
            });
            break;
        default:
            sorted.sort((a, b) => a.category.localeCompare(b.category));
    }
    return sorted;
}

/**
 * Filter history data
 */
function filterHistoryData(data, filterType, searchTerm) {
    let filtered = [...data];

    // Apply coverage filter
    if (filterType !== 'all') {
        filtered = filtered.filter(cat => {
            const coverage = getCoveragePercent(cat);
            switch (filterType) {
                case 'high': return coverage >= 70;
                case 'medium': return coverage >= 30 && coverage < 70;
                case 'low': return coverage < 30;
                default: return true;
            }
        });
    }

    // Apply search filter
    if (searchTerm && searchTerm.trim()) {
        const term = searchTerm.toLowerCase().trim();
        filtered = filtered.filter(cat =>
            cat.category.toLowerCase().includes(term)
        );
    }

    return filtered;
}

/**
 * Render history cards based on current filters
 */
function renderHistoryCards() {
    const grid = document.getElementById('history-grid');
    const emptyState = document.getElementById('history-empty');
    const resultsCount = document.getElementById('history-results-count');

    const sortBy = document.getElementById('history-sort')?.value || 'name-asc';
    const filterType = document.getElementById('history-filter')?.value || 'all';
    const searchTerm = document.getElementById('history-search')?.value || '';

    // Apply filter and sort
    let processed = filterHistoryData(historyData, filterType, searchTerm);
    processed = sortHistoryData(processed, sortBy);

    // Clear grid
    grid.innerHTML = '';

    if (historyData.length === 0) {
        emptyState.classList.remove('hidden');
        grid.classList.add('hidden');
        if (resultsCount) resultsCount.textContent = '';
    } else if (processed.length === 0) {
        emptyState.classList.add('hidden');
        grid.classList.remove('hidden');
        grid.innerHTML = '<p class="history-empty"><i class="fa-solid fa-filter-circle-xmark"></i> No categories match your filters</p>';
        if (resultsCount) resultsCount.textContent = `Showing 0 of ${historyData.length} categories`;
    } else {
        emptyState.classList.add('hidden');
        grid.classList.remove('hidden');

        // Update results count
        if (resultsCount) {
            if (processed.length === historyData.length) {
                resultsCount.textContent = `Showing all ${historyData.length} categories`;
            } else {
                resultsCount.textContent = `Showing ${processed.length} of ${historyData.length} categories`;
            }
        }

        // Create cards
        processed.forEach(category => {
            const card = createHistoryCard(category);
            grid.appendChild(card);
        });
    }
}

/**
 * Initialize filter/sort controls
 */
function initHistoryControls() {
    const sortSelect = document.getElementById('history-sort');
    const filterSelect = document.getElementById('history-filter');
    const searchInput = document.getElementById('history-search');

    if (sortSelect) {
        sortSelect.addEventListener('change', renderHistoryCards);
    }

    if (filterSelect) {
        filterSelect.addEventListener('change', renderHistoryCards);
    }

    if (searchInput) {
        // Debounce search input
        let searchTimeout;
        searchInput.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(renderHistoryCards, 300);
        });
    }
}

/**
 * Load and display history
 */
async function loadHistory() {
    const grid = document.getElementById('history-grid');
    const emptyState = document.getElementById('history-empty');
    const refreshBtn = document.getElementById('refresh-history-btn');

    // Show loading state
    if (refreshBtn) {
        refreshBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Loading...';
        refreshBtn.disabled = true;
    }

    try {
        const data = await fetchHistory();
        historyData = data.categories || [];

        // Update summary with all data
        updateHistorySummary(historyData);

        // Render with current filters
        renderHistoryCards();

        // Initialize controls (only once)
        if (!loadHistory._controlsInitialized) {
            initHistoryControls();
            loadHistory._controlsInitialized = true;
        }

    } catch (error) {
        console.error('Failed to load history:', error);
        grid.innerHTML = '<p class="history-empty"><i class="fa-solid fa-exclamation-triangle"></i> Failed to load history</p>';
    } finally {
        // Reset button
        if (refreshBtn) {
            refreshBtn.innerHTML = '<i class="fa-solid fa-arrows-rotate"></i> Refresh';
            refreshBtn.disabled = false;
        }
    }
}

/**
 * Show custom delete confirmation modal
 * @returns {Promise<boolean>} Resolves with user's choice
 */
function showDeleteModal(categoryName) {
    return new Promise((resolve) => {
        const modal = document.getElementById('delete-modal');
        const categoryNameEl = document.getElementById('modal-category-name');
        const cancelBtn = document.getElementById('modal-cancel-btn');
        const confirmBtn = document.getElementById('modal-confirm-btn');

        // Set category name
        categoryNameEl.textContent = `"${categoryName}"`;

        // Show modal
        modal.classList.remove('hidden');

        // Handle cancel
        const handleCancel = () => {
            modal.classList.add('hidden');
            cleanup();
            resolve(false);
        };

        // Handle confirm
        const handleConfirm = () => {
            modal.classList.add('hidden');
            cleanup();
            resolve(true);
        };

        // Handle backdrop click
        const handleBackdropClick = (e) => {
            if (e.target.classList.contains('modal-backdrop')) {
                handleCancel();
            }
        };

        // Handle escape key
        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                handleCancel();
            }
        };

        // Cleanup event listeners
        const cleanup = () => {
            cancelBtn.removeEventListener('click', handleCancel);
            confirmBtn.removeEventListener('click', handleConfirm);
            modal.removeEventListener('click', handleBackdropClick);
            document.removeEventListener('keydown', handleEscape);
        };

        // Add event listeners
        cancelBtn.addEventListener('click', handleCancel);
        confirmBtn.addEventListener('click', handleConfirm);
        modal.addEventListener('click', handleBackdropClick);
        document.addEventListener('keydown', handleEscape);
    });
}

/**
 * Delete a category from the database
 */
async function deleteCategory(categoryName) {
    // Show custom confirmation modal
    const confirmed = await showDeleteModal(categoryName);

    if (!confirmed) {
        return;
    }

    try {
        const headers = {};
        if (_csrfToken) {
            headers['X-CSRF-Token'] = _csrfToken;
        }
        const response = await fetch(`/api/category/${encodeURIComponent(categoryName)}`, {
            method: 'DELETE',
            headers
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Delete failed');
        }

        // Show success message
        showStatus(`✓ Deleted ${data.deleted_files} files from "${categoryName}"`, 'success');
        setTimeout(hideStatus, 3000);

        // Refresh the history
        loadHistory();

    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
        console.error('Failed to delete category:', error);
    }
}

// ============ File Preview Modal ============

/**
 * Show file preview modal with image, metadata, and depicts suggestions
 * @param {string} fileTitle - File title (e.g., "File:Example.jpg")
 */
async function showFilePreview(fileTitle) {
    const modal = document.getElementById('file-preview-modal');
    const titleEl = document.getElementById('preview-file-title');
    const imageContainer = document.getElementById('preview-image-container');
    const metaGrid = document.getElementById('preview-meta-grid');
    const descriptionEl = document.getElementById('preview-description');
    const viewCommonsBtn = document.getElementById('preview-view-commons');
    const addDepictsBtn = document.getElementById('preview-add-depicts');
    const suggestsContent = document.getElementById('suggests-content');

    // Set title
    titleEl.textContent = fileTitle.replace('File:', '');
    _currentPreviewFile = fileTitle;

    // Set initial loading state
    imageContainer.innerHTML = `
        <div class="preview-image-loading">
            <div class="spinner"></div>
            <span>Loading preview...</span>
        </div>
    `;
    metaGrid.innerHTML = '';
    descriptionEl.classList.add('hidden');
    descriptionEl.textContent = '';
    suggestsContent.innerHTML = `
        <div class="suggests-loading">
            <div class="spinner-small"></div>
            <span>Analyzing filename for suggestions...</span>
        </div>
    `;

    // Set action links
    const commonsUrl = getCommonsUrl(fileTitle);
    viewCommonsBtn.href = commonsUrl;
    addDepictsBtn.href = commonsUrl + '#P180';

    // Show modal
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    // Set up close handlers
    const closeBtn = document.getElementById('preview-close-btn');
    const backdrop = modal.querySelector('.modal-backdrop');

    const closeHandler = () => closeFilePreview();
    const backdropHandler = () => closeFilePreview();
    const escHandler = (e) => { if (e.key === 'Escape') closeFilePreview(); };

    closeBtn.addEventListener('click', closeHandler);
    backdrop.addEventListener('click', backdropHandler);
    document.addEventListener('keydown', escHandler);

    // Store cleanup refs
    modal._cleanup = () => {
        closeBtn.removeEventListener('click', closeHandler);
        backdrop.removeEventListener('click', backdropHandler);
        document.removeEventListener('keydown', escHandler);
    };

    // Fetch file info asynchronously
    try {
        const response = await fetch(`/api/fileinfo/${encodeURIComponent(fileTitle)}`);
        const data = await response.json();

        if (!response.ok || data.error) {
            imageContainer.innerHTML = `
                <div class="preview-image-loading">
                    <i class="fa-solid fa-image" style="font-size: 48px; color: var(--color-text-muted);"></i>
                    <span>Preview not available</span>
                </div>
            `;
        } else {
            // Show image
            const thumbnailUrl = data.thumbnail_url || getThumbnailUrl(fileTitle, 800);
            imageContainer.innerHTML = `
                <img src="${thumbnailUrl}" 
                     alt="${escapeHtml(fileTitle.replace('File:', ''))}"
                     class="preview-image"
                     onerror="this.parentElement.innerHTML='<div class=\\'preview-image-loading\\'><i class=\\'fa-solid fa-image\\' style=\\'font-size: 48px; color: var(--color-text-muted);\\'></i><span>Image could not be loaded</span></div>'">
            `;

            // Populate metadata grid
            const metaItems = [];

            if (data.width && data.height) {
                metaItems.push({ label: 'Dimensions', value: `${data.width} × ${data.height} px` });
            }
            if (data.size) {
                const sizeKB = (data.size / 1024).toFixed(1);
                const sizeMB = (data.size / (1024 * 1024)).toFixed(2);
                metaItems.push({ label: 'File Size', value: data.size > 1048576 ? `${sizeMB} MB` : `${sizeKB} KB` });
            }
            if (data.mime) {
                metaItems.push({ label: 'Format', value: data.mime });
            }
            if (data.timestamp) {
                const date = new Date(data.timestamp);
                metaItems.push({ label: 'Uploaded', value: date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) });
            }
            if (data.user) {
                metaItems.push({ label: 'Author', value: data.user });
            }
            if (data.license) {
                metaItems.push({ label: 'License', value: data.license });
            }

            metaGrid.innerHTML = metaItems.map(item => `
                <div class="preview-meta-item">
                    <span class="preview-meta-label">${item.label}</span>
                    <span class="preview-meta-value">${escapeHtml(item.value)}</span>
                </div>
            `).join('');

            // Show description if available
            if (data.description && data.description.trim()) {
                descriptionEl.textContent = data.description;
                descriptionEl.classList.remove('hidden');
            }
        }
    } catch (error) {
        console.error('Failed to fetch file info:', error);
        imageContainer.innerHTML = `
            <div class="preview-image-loading">
                <i class="fa-solid fa-triangle-exclamation" style="font-size: 48px; color: var(--color-warning);"></i>
                <span>Failed to load preview</span>
            </div>
        `;
    }

    // Fetch suggests asynchronously (runs in parallel-ish)
    loadSuggestions(fileTitle, suggestsContent);
}

/**
 * Close the file preview modal
 */
function closeFilePreview() {
    const modal = document.getElementById('file-preview-modal');
    modal.classList.add('hidden');
    document.body.style.overflow = '';
    if (modal._cleanup) {
        modal._cleanup();
        modal._cleanup = null;
    }
}

/**
 * Load Wikidata depicts suggestions for a file
 * @param {string} fileTitle - File title
 * @param {HTMLElement} container - Container element for suggestions
 */
async function loadSuggestions(fileTitle, container) {
    try {
        const response = await fetch(`/api/suggests/${encodeURIComponent(fileTitle)}`);
        const data = await response.json();

        if (!response.ok || !data.suggestions || data.suggestions.length === 0) {
            container.innerHTML = `<p class="suggests-empty">No suggestions found for this filename.</p>`;
            return;
        }

        const chipsHtml = data.suggestions.map(s => `
            <div class="suggest-chip">
                <div class="suggest-info">
                    <span class="suggest-label">${escapeHtml(s.label)}</span>
                    <span class="suggest-qid">${escapeHtml(s.qid)}</span>
                    ${s.description ? `<span class="suggest-desc" title="${escapeHtml(s.description)}">${escapeHtml(s.description)}</span>` : ''}
                </div>
                <div style="display:flex; gap:4px;">
                    ${_isLoggedIn ? `<button class="suggest-copy-btn" onclick="addDepictsFromSuggest('${escapeHtml(s.qid)}', '${escapeHtml(s.label).replace(/'/g, "\\'")}'  , this)" title="Add depicts">
                        <i class="fa-solid fa-plus"></i> Add
                    </button>` : ''}
                    <button class="suggest-copy-btn" onclick="copySuggestQid('${escapeHtml(s.qid)}', this)" title="Copy QID">
                        <i class="fa-solid fa-copy"></i> Copy
                    </button>
                </div>
            </div>
        `).join('');

        container.innerHTML = `<div class="suggests-list">${chipsHtml}</div>`;

    } catch (error) {
        console.error('Failed to load suggestions:', error);
        container.innerHTML = `<p class="suggests-error"><i class="fa-solid fa-circle-exclamation"></i> Failed to load suggestions</p>`;
    }
}

/**
 * Copy a Q-ID to clipboard with visual feedback
 * @param {string} qid - Wikidata Q-ID
 * @param {HTMLElement} btn - The button element for visual feedback
 */
function copySuggestQid(qid, btn) {
    navigator.clipboard.writeText(qid).then(() => {
        btn.classList.add('copied');
        btn.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
        setTimeout(() => {
            btn.classList.remove('copied');
            btn.innerHTML = '<i class="fa-solid fa-copy"></i> Copy';
        }, 2000);
    }).catch(() => {
        // Fallback for browsers without clipboard API
        const textArea = document.createElement('textarea');
        textArea.value = qid;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        btn.classList.add('copied');
        btn.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
        setTimeout(() => {
            btn.classList.remove('copied');
            btn.innerHTML = '<i class="fa-solid fa-copy"></i> Copy';
        }, 2000);
    });
}

// ============ Auth Functions ============

/** Track auth state globally */
let _isLoggedIn = false;
let _csrfToken = '';
let _currentPreviewFile = '';

/**
 * Check auth status on page load and update UI
 */
async function checkAuthStatus() {
    try {
        const response = await fetch('/auth/status');
        const data = await response.json();

        const authBtn = document.getElementById('auth-btn');
        const authLabel = document.getElementById('auth-label');

        if (data.logged_in) {
            _isLoggedIn = true;
            _csrfToken = data.csrf_token || '';
            authBtn.classList.add('logged-in');
            authBtn.href = '/auth/logout';
            authBtn.title = `Logged in as ${data.username}. Click to logout.`;
            authLabel.textContent = data.username;
            authBtn.querySelector('i').className = 'fa-solid fa-user-check';
        } else {
            _isLoggedIn = false;
            authBtn.classList.remove('logged-in');
            authBtn.href = '/auth/login';
            authBtn.title = data.oauth_configured
                ? 'Login with Wikimedia'
                : 'OAuth not configured';
            authLabel.textContent = 'Login';
            authBtn.querySelector('i').className = 'fa-solid fa-user';
        }
    } catch (error) {
        console.error('Auth check failed:', error);
    }
}

/**
 * Add a depicts statement from a suggestion chip
 * @param {string} qid - Wikidata QID
 * @param {string} label - Label of the entity 
 * @param {HTMLElement} btn - The button element
 */
async function addDepictsFromSuggest(qid, label, btn) {
    if (!_isLoggedIn) {
        showToast('Please log in with Wikimedia first', 'warning');
        return;
    }

    if (!_currentPreviewFile) {
        showToast('No file selected', 'error');
        return;
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Adding...';

    try {
        const response = await fetch('/api/add-depicts', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': _csrfToken
            },
            body: JSON.stringify({ file_title: _currentPreviewFile, qid: qid })
        });

        const data = await response.json();

        if (data.success) {
            btn.classList.add('copied');
            btn.innerHTML = '<i class="fa-solid fa-check"></i> Added!';
            showToast(`Added "${label}" (${qid}) as depicts`, 'success');
        } else {
            btn.innerHTML = '<i class="fa-solid fa-xmark"></i> Failed';
            showToast(`Failed: ${data.error}`, 'error');
            setTimeout(() => {
                btn.disabled = false;
                btn.innerHTML = `<i class="fa-solid fa-plus"></i> Add`;
            }, 3000);
        }
    } catch (error) {
        console.error('Add depicts failed:', error);
        btn.innerHTML = '<i class="fa-solid fa-xmark"></i> Error';
        showToast('Network error adding depicts', 'error');
        setTimeout(() => {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-plus"></i> Add`;
        }, 3000);
    }
}

// Check auth status on page load
checkAuthStatus();

// Make functions globally accessible for inline onclick handlers
window.deleteCategory = deleteCategory;
window.reanalyzeCategory = reanalyzeCategory;
window.showFilePreview = showFilePreview;
window.copySuggestQid = copySuggestQid;
window.addDepictsFromSuggest = addDepictsFromSuggest;
