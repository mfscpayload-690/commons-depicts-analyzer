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
});
