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
    // Tables
    tableWithDepicts: document.getElementById('table-with-depicts'),
    tableWithoutDepicts: document.getElementById('table-without-depicts'),
    emptyWith: document.getElementById('empty-with'),
    emptyWithout: document.getElementById('empty-without'),
    // Tabs
    countWith: document.getElementById('count-with'),
    countWithout: document.getElementById('count-without'),
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
    elements.analyzeBtn.disabled = isLoading;
    elements.categoryInput.disabled = isLoading;
    if (isLoading) {
        elements.analyzeBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analyzing...';
    } else {
        elements.analyzeBtn.innerHTML = '<i class="fa-solid fa-bolt"></i> Analyze';
    }
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

async function handleSubmit(event) {
    event.preventDefault();

    const category = elements.categoryInput.value.trim();
    if (!category) {
        showStatus('Please enter a category name', 'error');
        return;
    }

    setLoading(true);
    showStatus(`Analyzing "${category}"... This may take a moment for large categories.`, 'loading');

    // Hide previous results
    elements.statisticsSection.classList.add('hidden');
    elements.resultsSection.classList.add('hidden');

    try {
        const result = await analyzeCategory(category);

        hideStatus();
        updateStatistics(result.statistics);
        populateTables(result.files);

        showStatus(`Analysis complete! Found ${result.statistics.total} files.`, 'success');
        setTimeout(hideStatus, 3000);

    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
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

    // Refresh history button
    const refreshBtn = document.getElementById('refresh-history-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadHistory);
    }
});

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
        const categories = data.categories || [];

        // Clear grid
        grid.innerHTML = '';

        if (categories.length === 0) {
            emptyState.classList.remove('hidden');
            grid.classList.add('hidden');
            updateHistorySummary([]);
        } else {
            emptyState.classList.add('hidden');
            grid.classList.remove('hidden');

            // Update summary
            updateHistorySummary(categories);

            // Create cards
            categories.forEach(category => {
                const card = createHistoryCard(category);
                grid.appendChild(card);
            });
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
