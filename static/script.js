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
                <a href="/watch/${video.video_id}" class="video-link" data-video-id="${video.video_id}">
                    <img src="${video.local_thumbnail}" alt="${escapeHtml(video.title)}">
                </a>
                <div class="card-body">
                    <h3 class="card-title">${escapeHtml(video.title)}</h3>
                    <div class="card-channel">${escapeHtml(video.channel)}</div>
                </div>`;
            
            // Attach safety interceptor to the card's link
            const link = card.querySelector('.video-link');
            link.addEventListener('click', function(e) {
                e.preventDefault(); // Pause standard navigation momentarily
                const videoId = this.getAttribute('data-video-id');

                // Check video safety status before letting the user navigate
                fetch(`/videos/${videoId}`)
                    .then(response => {
                        if (response.status === 403) {
                            alert("Playback blocked: This video violated content guidelines.");
                            window.location.href = "/";
                        } else if (response.ok || response.status === 404) {
                            // If safe (or 404 handled elsewhere), proceed to watch page normally
                            window.location.href = `/watch/${videoId}`;
                        }
                    })
                    .catch(err => {
                        console.error("Error validating video safety:", err);
                        // Fallback navigation if network hiccups occur
                        window.location.href = `/watch/${videoId}`;
                    });
            });

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