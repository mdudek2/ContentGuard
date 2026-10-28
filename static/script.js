let eventSource = null;

function startSearch(event) {
    event.preventDefault();
    const query = document.getElementById('search-query').value.trim();
    if (!query) return;

    const container = document.getElementById('results-container');
    container.innerHTML = '';
    if (eventSource) {
        eventSource.close();
    }

    const loader = document.getElementById('loading-indicator');
    loader.style.display = 'flex';

    eventSource = new EventSource(`/stream-search?q=${encodeURIComponent(query)}`);

    eventSource.onmessage = function(event) {
        if (event.data === "[DONE]") {
            loader.style.display = 'none';
            eventSource.close();
            return;
        }

        try {
            const video = JSON.parse(event.data);
            
            const card = document.createElement('div');
            card.className = 'card';
            card.innerHTML = `
                <a href="https://www.youtube.com/watch?v=${video.video_id}" target="_blank">
                    <img src="${video.local_thumbnail}" alt="${escapeHtml(video.title)}">
                </a>
                <div class="card-body">
                    <h3 class="card-title">${escapeHtml(video.title)}</h3>
                    <div class="card-channel">${escapeHtml(video.channel)}</div>
                </div>
            `;
            container.appendChild(card);
        } catch (err) {
            console.error("Failed to parse incoming video payload", err);
        }
    };

    eventSource.onerror = function(err) {
        console.error("EventSource failed:", err);
        loader.style.display = 'none';
        if (eventSource) {
            eventSource.close();
        }
    };
}

function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}