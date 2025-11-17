const params = new URLSearchParams(window.location.search);
const hostParam = params.get('host');
const decodedHost = hostParam ? decodeURIComponent(hostParam) : '';

let nodeEvents = [];
const nodeFilters = {
    severity: 'all',
    category: 'all',
    sort: 'newest'
};

async function initNodePage() {
    if (!decodedHost) {
        showNodeError('Missing host parameter.');
        return;
    }

    document.getElementById('node-name').textContent = decodedHost;
    setupNodeFilters();

    try {
        const [statsResp, eventsResp] = await Promise.all([
            fetch('/api/stats'),
            fetch(`/api/events/${encodeURIComponent(decodedHost)}`)
        ]);

        if (!statsResp.ok) {
            throw new Error(`Failed to load stats (HTTP ${statsResp.status})`);
        }

        if (!eventsResp.ok) {
            throw new Error(`Failed to load events (HTTP ${eventsResp.status})`);
        }

        const stats = await statsResp.json();
        const events = await eventsResp.json();

        nodeEvents = Array.isArray(events) ? events : [];

        updateNodeMeta(stats.nodes || [], nodeEvents);
        renderNodeEvents();
    } catch (error) {
        showNodeError(error.message);
    } finally {
        document.getElementById('node-loading').style.display = 'none';
    }
}

function setupNodeFilters() {
    const severityFilter = document.getElementById('node-severity-filter');
    const categoryFilter = document.getElementById('node-category-filter');
    const resetButton = document.getElementById('node-reset-filters');
    const sortFilter = document.getElementById('node-sort-filter');

    if (severityFilter) {
        severityFilter.addEventListener('change', (e) => {
            nodeFilters.severity = e.target.value;
            renderNodeEvents();
        });
    }

    if (categoryFilter) {
        categoryFilter.addEventListener('change', (e) => {
            nodeFilters.category = e.target.value;
            renderNodeEvents();
        });
    }

    if (resetButton) {
        resetButton.addEventListener('click', () => {
            nodeFilters.severity = 'all';
            nodeFilters.category = 'all';
            nodeFilters.sort = 'newest';
            if (severityFilter) {
                severityFilter.value = 'all';
            }
            if (categoryFilter) {
                categoryFilter.value = 'all';
            }
            if (sortFilter) {
                sortFilter.value = 'newest';
            }
            renderNodeEvents();
        });
    }

    if (sortFilter) {
        sortFilter.addEventListener('change', (e) => {
            nodeFilters.sort = e.target.value;
            renderNodeEvents();
        });
    }
}

function updateNodeMeta(nodes, events) {
    const meta = nodes.find(node => node.host === decodedHost);
    const total = meta ? meta.total_events : events.length;
    const lastEvent = meta && meta.last_event_time
        ? formatEventTimestamp(meta.last_event_time)
        : (events[0] ? formatEventTimestamp(events[0].time) : 'No events yet');

    document.getElementById('node-ip').textContent = meta ? `IP: ${meta.host_ipv4}` : 'IP: Unknown';
    document.getElementById('node-total').textContent = `${total} event${total === 1 ? '' : 's'}`;
    document.getElementById('node-last').textContent = `Last event: ${lastEvent}`;
}

function renderNodeEvents() {
    const section = document.getElementById('node-events-section');
    const emptyState = document.getElementById('node-empty');
    const container = document.getElementById('node-events');
    const title = document.getElementById('node-events-title');

    if (!nodeEvents.length) {
        section.style.display = 'none';
        emptyState.style.display = 'block';
        return;
    }

    const filteredEvents = getFilteredNodeEvents();

    if (!filteredEvents.length) {
        section.style.display = 'block';
        emptyState.style.display = 'none';
        container.innerHTML = '<div class="no-results">No events match the selected filters.</div>';
        if (title) {
            title.textContent = 'Node Events (0)';
        }
        return;
    }

    section.style.display = 'block';
    emptyState.style.display = 'none';

    container.innerHTML = filteredEvents.map(event => createEventMarkup(event)).join('');

    if (title) {
        title.textContent = filteredEvents.length === nodeEvents.length
            ? 'Node Events'
            : `Node Events (${filteredEvents.length} of ${nodeEvents.length})`;
    }
}

function getFilteredNodeEvents() {
    if (!nodeEvents.length) {
        return [];
    }

    let filtered = [...nodeEvents];

    filtered.sort((a, b) => new Date(b.time) - new Date(a.time));
    if (nodeFilters.sort === 'oldest') {
        filtered.reverse();
    }

    if (nodeFilters.severity !== 'all') {
        filtered = filtered.filter(event =>
            event.severity.toLowerCase() === nodeFilters.severity.toLowerCase()
        );
    }

    if (nodeFilters.category !== 'all') {
        filtered = filtered.filter(event =>
            event.category.toLowerCase() === nodeFilters.category.toLowerCase()
        );
    }

    return filtered;
}

function createEventMarkup(event) {
    const timeStr = formatEventTimestamp(event.time);

    return `
        <div class="event-item severity-${event.severity}">
            <div class="event-header">
                <div class="event-type">[${event.category.toUpperCase()}] ${formatEventType(event.event_type)}</div>
                <div class="event-time">${timeStr}</div>
            </div>
            <div class="event-message">${event.message}</div>
            <div class="event-meta">
                <span>Severity: ${event.severity}</span>
                <span>Source: ${event.source}</span>
            </div>
        </div>
    `;
}

function formatEventTimestamp(timestamp) {
    if (!timestamp) {
        return new Date().toLocaleString();
    }

    const parsed = Date.parse(timestamp);
    if (Number.isNaN(parsed)) {
        return `${timestamp} (raw)`;
    }

    return new Date(parsed).toLocaleString();
}

function formatEventType(eventType) {
    return eventType
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

function showNodeError(message) {
    const errorEl = document.getElementById('node-error');
    document.getElementById('node-error-message').textContent = message;
    errorEl.style.display = 'block';
}

document.addEventListener('DOMContentLoaded', initNodePage);
