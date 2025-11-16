// Dashboard state
let charts = {};
let allRecentEvents = []; // Store all events for filtering
let allNodes = [];
let showAllNodes = false;
let currentFilters = {
    severity: 'all',
    category: 'all'
};
const REFRESH_INTERVAL = 5000; // 5 seconds

// Color schemes for categories
const CATEGORY_COLORS = {
    authentication: ['#3498db', '#2980b9', '#5dade2', '#85c1e9', '#aed6f1', '#d6eaf8'],
    privilege_escalation: ['#e67e22', '#d35400', '#f39c12', '#f1c40f', '#f4d03f', '#f7dc6f'],
    remote_access: ['#9b59b6', '#8e44ad', '#af7ac5', '#bb8fce', '#c39bd3', '#d2b4de'],
    system: ['#e74c3c', '#c0392b', '#ec7063', '#f1948a', '#f5b7b1', '#fadbd8'],
    service: ['#16a085', '#138d75', '#48c9b0', '#76d7c4', '#a2d9ce', '#d1f2eb'],
    software: ['#2ecc71', '#27ae60', '#58d68d', '#82e0aa', '#abebc6', '#d5f4e6']
};

// Initialize dashboard
async function init() {
    console.log('[INFO] Initializing dashboard...');

    // Setup filter event listeners
    setupFilters();
    setupNodesUI();

    await fetchAndUpdate();
    // Auto-refresh every 5 seconds
    setInterval(fetchAndUpdate, REFRESH_INTERVAL);
}

// Setup filter controls
function setupFilters() {
    const severityFilter = document.getElementById('severity-filter');
    const categoryFilter = document.getElementById('category-filter');
    const resetButton = document.getElementById('reset-filters');

    severityFilter.addEventListener('change', (e) => {
        currentFilters.severity = e.target.value;
        applyFilters();
    });

    categoryFilter.addEventListener('change', (e) => {
        currentFilters.category = e.target.value;
        applyFilters();
    });

    resetButton.addEventListener('click', () => {
        severityFilter.value = 'all';
        categoryFilter.value = 'all';
        currentFilters.severity = 'all';
        currentFilters.category = 'all';
        applyFilters();
    });
}

function setupNodesUI() {
    const toggleButton = document.getElementById('toggle-nodes');
    if (!toggleButton) return;

    toggleButton.addEventListener('click', () => {
        showAllNodes = !showAllNodes;
        renderNodes();
    });
}

// Fetch data and update dashboard
async function fetchAndUpdate() {
    try {
        const response = await fetch('/api/stats');

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        console.log('[INFO] Received stats:', data);

        // Hide loading, show content
        document.getElementById('loading').style.display = 'none';
        document.getElementById('error').style.display = 'none';

        if (data.total_events === 0) {
            document.getElementById('no-data').style.display = 'block';
            document.getElementById('categories').innerHTML = '';
            document.getElementById('recent-events-section').style.display = 'none';
        } else {
            document.getElementById('no-data').style.display = 'none';
            updateDashboard(data);
        }

    } catch (error) {
        console.error('[ERROR] Failed to fetch stats:', error);
        document.getElementById('loading').style.display = 'none';
        document.getElementById('error').style.display = 'block';
        document.getElementById('error-message').textContent = error.message;
    }
}

// Update dashboard with new data
function updateDashboard(data) {
    // Update header stats
    document.getElementById('total-events').textContent = data.total_events.toLocaleString();

    const lastUpdated = new Date(data.last_updated);
    document.getElementById('last-updated').textContent = lastUpdated.toLocaleTimeString();

    // Update categories
    updateCategories(data.categories);

    // Update nodes
    updateNodes(data.nodes || []);

    // Update recent events
    updateRecentEvents(data.categories);
}

// Update categories grid
function updateCategories(categories) {
    const container = document.getElementById('categories');
    container.innerHTML = '';

    categories.forEach(category => {
        const card = createCategoryCard(category);
        container.appendChild(card);
    });
}

// Create a category card
function createCategoryCard(category) {
    const card = document.createElement('div');
    card.className = 'category-card';

    // Determine severity class based on event severity distribution
    const severityClass = getMostSevereSeverity(category.severity_counts);

    card.innerHTML = `
        <div class="category-header">
            <div class="category-name">${category.category}</div>
            <div class="category-count ${severityClass}">${category.total_count}</div>
        </div>
        <div class="chart-container">
            <canvas id="chart-${category.category}"></canvas>
        </div>
        <div class="event-types">
            <h4>Event Types</h4>
            ${createEventTypesList(category.event_types)}
        </div>
    `;

    // Create pie chart after DOM insertion
    setTimeout(() => {
        createPieChart(category.category, category.event_types);
    }, 0);

    return card;
}

// Create event types list
function createEventTypesList(eventTypes) {
    const sorted = Object.entries(eventTypes).sort((a, b) => b[1] - a[1]);

    return sorted.map(([type, count]) => `
        <div class="event-type-item">
            <div class="event-type-name">${formatEventType(type)}</div>
            <div class="event-type-count">${count}</div>
        </div>
    `).join('');
}

// Create pie chart for category
function createPieChart(category, eventTypes) {
    const canvasId = `chart-${category}`;
    const canvas = document.getElementById(canvasId);

    if (!canvas) {
        console.error(`[ERROR] Canvas not found: ${canvasId}`);
        return;
    }

    // Destroy existing chart if it exists
    if (charts[category]) {
        charts[category].destroy();
    }

    const ctx = canvas.getContext('2d');
    const labels = Object.keys(eventTypes).map(formatEventType);
    const values = Object.values(eventTypes);
    const colors = CATEGORY_COLORS[category] || CATEGORY_COLORS.auth;

    charts[category] = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: colors,
                borderWidth: 2,
                borderColor: 'white'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        boxWidth: 12,
                        font: {
                            size: 11
                        },
                        padding: 10
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

// Update recent events section
function updateRecentEvents(categories) {
    const section = document.getElementById('recent-events-section');

    // Collect all recent events from all categories
    allRecentEvents = [];
    categories.forEach(category => {
        allRecentEvents = allRecentEvents.concat(category.recent_events);
    });

    // Sort by time (most recent first)
    allRecentEvents.sort((a, b) => new Date(b.time) - new Date(a.time));

    if (allRecentEvents.length === 0) {
        section.style.display = 'none';
        return;
    }

    section.style.display = 'block';

    // Apply current filters
    applyFilters();
}

// Apply filters to recent events
function applyFilters() {
    const container = document.getElementById('recent-events');

    // Filter events based on current filters
    let filteredEvents = allRecentEvents;

    // Filter by severity
    if (currentFilters.severity !== 'all') {
        filteredEvents = filteredEvents.filter(event =>
            event.severity.toLowerCase() === currentFilters.severity.toLowerCase()
        );
    }

    // Filter by category
    if (currentFilters.category !== 'all') {
        filteredEvents = filteredEvents.filter(event =>
            event.category.toLowerCase() === currentFilters.category.toLowerCase()
        );
    }

    // Take top 50 (increased from 10 to show more filtered results)
    filteredEvents = filteredEvents.slice(0, 50);

    // Update display
    if (filteredEvents.length === 0) {
        container.innerHTML = '<div class="no-results">No events match the selected filters.</div>';
    } else {
        container.innerHTML = filteredEvents.map(event => createEventItem(event)).join('');
    }

    // Update filter count indicator
    updateFilterCount(filteredEvents.length, allRecentEvents.length);
}

// Update filter count display
function updateFilterCount(filtered, total) {
    const header = document.querySelector('.recent-events-header h2');
    if (filtered === total) {
        header.textContent = 'Recent Events';
    } else {
        header.textContent = `Recent Events (${filtered} of ${total})`;
    }
}

function updateNodes(nodes = []) {
    const section = document.getElementById('nodes-section');
    const toggleButton = document.getElementById('toggle-nodes');

    allNodes = nodes || [];

    if (!section) {
        return;
    }

    if (!allNodes.length) {
        section.style.display = 'none';
        if (toggleButton) {
            toggleButton.style.display = 'none';
        }
        return;
    }

    section.style.display = 'block';
    renderNodes();
}

function renderNodes() {
    const grid = document.getElementById('nodes-grid');
    const toggleButton = document.getElementById('toggle-nodes');

    if (!grid) {
        return;
    }

    grid.innerHTML = '';

    const nodesToShow = showAllNodes ? allNodes : allNodes.slice(0, 4);

    nodesToShow.forEach(node => {
        grid.appendChild(createNodeCard(node));
    });

    if (!toggleButton) {
        return;
    }

    if (allNodes.length <= 4) {
        toggleButton.style.display = 'none';
    } else {
        toggleButton.style.display = 'inline-flex';
        toggleButton.textContent = showAllNodes ? 'Show Top Nodes' : 'Show All Nodes';
    }
}

function createNodeCard(node) {
    const card = document.createElement('div');
    card.className = 'node-card';

    const lastEventText = node.last_event_time
        ? formatEventTimestamp(node.last_event_time)
        : 'No events yet';

    const severitySummary = formatSeveritySummary(node.severity_counts || {});
    const categorySummary = formatCategorySummary(node.categories || {});

    card.innerHTML = `
        <div class="node-name">${node.host}</div>
        <div class="node-ip">${node.host_ipv4}</div>
        <div class="node-count">${node.total_events.toLocaleString()} events</div>
        <div class="node-metadata">
            <span>Last event: ${lastEventText}</span>
            <span>Categories: ${categorySummary}</span>
            <span>Severity: ${severitySummary}</span>
        </div>
    `;

    card.addEventListener('click', () => navigateToNode(node.host));

    const button = document.createElement('button');
    button.className = 'node-view-button';
    button.textContent = 'View Logs';
    button.addEventListener('click', (event) => {
        event.stopPropagation();
        navigateToNode(node.host);
    });

    card.appendChild(button);

    return card;
}

function navigateToNode(host) {
    window.location.href = `/node.html?host=${encodeURIComponent(host)}`;
}

function formatSeveritySummary(counts) {
    if (!counts || Object.keys(counts).length === 0) {
        return 'No severity data';
    }

    const order = ['critical', 'error', 'warning', 'info'];
    const summary = order
        .filter(sev => counts[sev])
        .map(sev => `${sev}: ${counts[sev]}`)
        .join(' • ');

    return summary || 'Severity data unavailable';
}

function formatCategorySummary(counts) {
    if (!counts || Object.keys(counts).length === 0) {
        return 'No categories';
    }

    const entries = Object.entries(counts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([name, value]) => `${formatEventType(name)} (${value})`);

    const remainder = Object.keys(counts).length - entries.length;
    if (remainder > 0) {
        entries.push(`+${remainder} more`);
    }

    return entries.join(', ');
}

// Create event item HTML
function formatEventTimestamp(timestamp) {
    if (!timestamp) {
        return new Date().toLocaleString();
    }

    const parsed = Date.parse(timestamp);
    if (Number.isNaN(parsed)) {
        // Fall back to rendering the original string so users still see something meaningful
        return `${timestamp} (raw)`;
    }

    return new Date(parsed).toLocaleString();
}

function createEventItem(event) {
    const timeStr = formatEventTimestamp(event.time);

    return `
        <div class="event-item severity-${event.severity}">
            <div class="event-header">
                <div class="event-type">[${event.category.toUpperCase()}] ${formatEventType(event.event_type)}</div>
                <div class="event-time">${timeStr}</div>
            </div>
            <div class="event-message">${event.message}</div>
            <div class="event-meta">
                <span>Host: ${event.host}</span>
                <span>IP: ${event.host_ipv4}</span>
                <span>Severity: ${event.severity}</span>
            </div>
        </div>
    `;
}

// Format event type name (convert snake_case to Title Case)
function formatEventType(eventType) {
    return eventType
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

// Get most severe severity from counts
function getMostSevereSeverity(severityCounts) {
    if (!severityCounts) return 'info';

    const severityOrder = ['critical', 'error', 'warning', 'info'];

    for (const severity of severityOrder) {
        if (severityCounts[severity] && severityCounts[severity] > 0) {
            return severity;
        }
    }

    return 'info';
}

// Start the dashboard when page loads
document.addEventListener('DOMContentLoaded', init);
