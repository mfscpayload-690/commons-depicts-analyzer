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

let suggestionItems = [];
let activeSuggestionIndex = -1;
let suggestionTimeout;
let activeJobId = null;

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
 * Start an async analysis job
 * @param {string} category - Category name
 * @returns {Promise<Object>} Job response
 */
async function startAnalysisJob(category) {
    const response = await fetch('/api/analyze?async=1', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ category }),
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || 'Failed to start analysis');
    }

    return data;
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
async function fetchSuggestions(query) {
    const response = await fetch(`/api/suggest?query=${encodeURIComponent(query)}`);
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
 * Populate files table
 * @param {Array} files - Array of file objects
 */
function populateTables(files) {
    const withDepicts = files.filter(f => f.has_depicts);
    const withoutDepicts = files.filter(f => !f.has_depicts);

    // Update counts
    elements.countWith.textContent = withDepicts.length;
    elements.countWithout.textContent = withoutDepicts.length;

    // Populate "without depicts" table
    const tbodyWithout = elements.tableWithoutDepicts.querySelector('tbody');
    tbodyWithout.innerHTML = '';

    if (withoutDepicts.length === 0) {
        elements.tableWithoutDepicts.classList.add('hidden');
        elements.emptyWithout.classList.remove('hidden');
    } else {
        elements.tableWithoutDepicts.classList.remove('hidden');
        elements.emptyWithout.classList.add('hidden');

        withoutDepicts.forEach((file, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${index + 1}</td>
                <td class="file-link">
                    <a href="${getCommonsUrl(file.file_name)}" target="_blank" rel="noopener">
                        ${escapeHtml(file.file_name.replace('File:', ''))}
                    </a>
                </td>
                <td>
                    <a href="${getCommonsUrl(file.file_name)}#P180" target="_blank" rel="noopener" 
                       title="Add depicts on Commons">
                        + Add depicts
                    </a>
                </td>
            `;
            tbodyWithout.appendChild(row);
        });
    }

    // Populate "with depicts" table
    const tbodyWith = elements.tableWithDepicts.querySelector('tbody');
    tbodyWith.innerHTML = '';

    if (withDepicts.length === 0) {
        elements.tableWithDepicts.classList.add('hidden');
        elements.emptyWith.classList.remove('hidden');
    } else {
        elements.tableWithDepicts.classList.remove('hidden');
        elements.emptyWith.classList.add('hidden');

        withDepicts.forEach((file, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${index + 1}</td>
                <td class="file-link">
                    <a href="${getCommonsUrl(file.file_name)}" target="_blank" rel="noopener">
                        ${escapeHtml(file.file_name.replace('File:', ''))}
                    </a>
                </td>
                <td class="depicts-cell">${escapeHtml(file.depicts || '')}</td>
            `;
            tbodyWith.appendChild(row);
        });
    }

    elements.resultsSection.classList.remove('hidden');
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
        detail = `Processed ${status.processed || 0} of ${status.total} files`;
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
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'history-chip';
        chip.textContent = name;
        chip.addEventListener('click', () => {
            elements.categoryInput.value = name;
            elements.form.dispatchEvent(new Event('submit'));
        });
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

function clearSearchHistory() {
    localStorage.removeItem(SEARCH_HISTORY_KEY);
    renderSearchHistory([]);
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
        renderSuggestionsEmpty();
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
        showStatus('Please enter a category name', 'error');
        return;
    }

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

        updateStatistics(result.statistics);
        populateTables(result.files);
        saveSearchHistory(category);

        showStatus(`Analysis complete! Found ${result.statistics.total} files.`, 'success');
        setTimeout(hideStatus, 3000);
        completeProgress();

    } catch (error) {
        if (error.message === 'Analysis canceled') return;
        showStatus(`Error: ${error.message}`, 'error');
        hideProgress();
    } finally {
        setLoading(false);
    }
}

// ============ Initialization ============

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
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
        });
    });
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
        initHistoryControls();

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
        const response = await fetch(`/api/category/${encodeURIComponent(categoryName)}`, {
            method: 'DELETE'
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

// Make functions globally accessible for inline onclick handlers
window.deleteCategory = deleteCategory;
window.reanalyzeCategory = reanalyzeCategory;
