function injectOverlay() {
    if (document.getElementById('yt-python-downloader-overlay')) return;

    const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
    if (!player) return;

    // Inject CSS style for auto-hide matching YouTube's controls overlay
    if (!document.getElementById('yt-python-downloader-styles')) {
        const style = document.createElement('style');
        style.id = 'yt-python-downloader-styles';
        style.innerHTML = `
            #yt-python-downloader-overlay {
                position: absolute;
                top: 10px;
                right: 10px;
                z-index: 2000;
                background: rgba(28, 28, 28, 0.85);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 3px 6px;
                font-family: 'Roboto', 'Arial', sans-serif;
                font-size: 10px;
                font-weight: 400;
                color: #f1f1f1;
                display: flex;
                align-items: center;
                gap: 5px;
                box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
                opacity: 1;
                pointer-events: auto;
                transition: opacity 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            }
           
            .yt-downloader-link {
                color: #3B82F6;
                text-decoration: none;
                cursor: pointer;
                padding: 2px 4px;
                border-radius: 3px;
                transition: background-color 0.2s, color 0.2s;
            }
            .yt-downloader-link:hover {
                background-color: rgba(59, 130, 246, 0.15);
                color: #60A5FA;
                text-decoration: underline;
            }
            .yt-downloader-sep {
                color: rgba(255, 255, 255, 0.3);
            }
            .yt-downloader-status {
                font-style: italic;
                font-size: 11px;
                color: #10B981;
                margin-left: 5px;
            }
        `;
        document.head.appendChild(style);
    }

    const overlay = document.createElement('div');
    overlay.id = 'yt-python-downloader-overlay';
    overlay.innerHTML = `
        <span style="display:flex;align-items:center;margin-right:4px;">
            <svg viewBox="0 0 24 24" width="14" height="14" style="fill:#3B82F6;margin-right:4px;"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>
            Download:
        </span>
        <a class="yt-downloader-link" data-quality="Best Quality (MP4)">MP4</a>
        <span class="yt-downloader-sep">|</span>
        <a class="yt-downloader-link" data-quality="Best Quality (MOV)">MOV</a>
        <span class="yt-downloader-sep">|</span>
        <a class="yt-downloader-link" data-quality="Audio Only (MP3)">MP3</a>
        <span id="yt-downloader-status-label" class="yt-downloader-status" style="display:none;"></span>
    `;

    // Bind link click handlers
    overlay.querySelectorAll('.yt-downloader-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.stopPropagation();
            const quality = link.getAttribute('data-quality');
            triggerDownload(quality);
        });
    });

    player.appendChild(overlay);
}

function triggerDownload(quality) {
    const videoId = new URLSearchParams(window.location.search).get('v');
    const videoUrl = videoId ? `https://www.youtube.com/watch?v=${videoId}` : window.location.href;
    const statusLabel = document.getElementById('yt-downloader-status-label');

    if (statusLabel) {
        statusLabel.innerText = "Sending...";
        statusLabel.style.color = "#EAB308";
        statusLabel.style.display = "inline";
    }

    // Try sending fetch to local HTTP server
    fetch(`http://127.0.0.1:30121/download?url=${encodeURIComponent(videoUrl)}&quality=${encodeURIComponent(quality)}`)
        .then(response => {
            if (response.ok) {
                if (statusLabel) {
                    statusLabel.innerText = "Sent!";
                    statusLabel.style.color = "#10B981";
                    setTimeout(() => { statusLabel.style.display = "none"; }, 3000);
                }
            } else {
                throw new Error("HTTP error");
            }
        })
        .catch(err => {
            // Server not running, trigger custom protocol fallback to autolaunch it!
            if (statusLabel) {
                statusLabel.innerText = "Launching App...";
                statusLabel.style.color = "#60A5FA";
                setTimeout(() => { statusLabel.style.display = "none"; }, 5000);
            }

            const iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.src = `youtubedownloader://download?url=${encodeURIComponent(videoUrl)}&quality=${encodeURIComponent(quality)}`;
            document.body.appendChild(iframe);
            setTimeout(() => iframe.remove(), 1000);
        });
}

function isWatchPage() {
    return window.location.pathname === '/watch';
}

function updateOverlay() {
    if (isWatchPage()) {
        injectOverlay();
    } else {
        const existing = document.getElementById('yt-python-downloader-overlay');
        if (existing) existing.remove();
    }
}

// YouTube is a single-page app: react to its navigation events and (debounced) DOM changes
let debounceTimer = null;
const observer = new MutationObserver(() => {
    if (debounceTimer) return;
    debounceTimer = setTimeout(() => {
        debounceTimer = null;
        updateOverlay();
    }, 300);
});

observer.observe(document.body, { childList: true, subtree: true });
window.addEventListener('yt-navigate-finish', updateOverlay);

// Initial call
updateOverlay();
