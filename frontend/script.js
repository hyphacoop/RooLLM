let isThinking = false;
let sessionId = null;

// Tool emoji mapping - loaded from shared constants
let emojiToolMap = {};

// Load tool constants from shared JSON file
async function loadToolConstants() {
    try {
        const response = await fetch("../tool_constants.json");
        if (response.ok) {
            const data = await response.json();
            const toolMap = data.emojiToolMap;

            // Convert to frontend format
            emojiToolMap = {};
            for (const [emoji, info] of Object.entries(toolMap)) {
                emojiToolMap[emoji] = `\`${info.tool}\`:  \n${info.description}`;
            }
            console.log("Loaded tool constants from shared file");
        } else {
            throw new Error(`HTTP ${response.status}`);
        }
    } catch (error) {
        console.warn("Could not load tool constants from shared file:", error);
        // Fallback to hardcoded mapping
        emojiToolMap = {
            "💬": "`comment_github_item`:  \nAdd comments to issues or PRs",
            "👤": "`assign_github_item`:  \nAssign users to issues or PRs",
            "🏷️": "`add_labels_to_github_item`:  \nAdd labels to issues or PRs",
            "🔖": "`search_repo_labels`:  \nGet available labels in a repository",
            "🔧": "`github_issues_operations`:  \nDispatcher for issue operations",
            "📝": "`create_github_issue`:  \nCreate new issues",
            "🔒": "`close_github_issue`:  \nClose an issue",
            "🔑": "`reopen_github_issue`:  \nReopen a closed issue",
            "🔍": "`search_github_issues`:  \nSearch for issues by status, number, assignee, etc.",
            "📋": "`update_github_issue`:  \nUpdate issue title/body",
            "🛠️": "`github_pull_requests_operations`:  \nDispatcher for PR operations",
            "🌿": "`create_pull_request`:  \nCreate new PRs",
            "🔐": "`close_pull_request`:  \nClose a PR without merging",
            "🔓": "`reopen_pull_request`:  \nReopen a closed PR",
            "🔀": "`merge_pull_request`:  \nMerge an open PR",
            "🔎": "`search_pull_requests`:  \nSearch for PRs by status, number, assignee, label, etc.",
            "✏️": "`update_pull_request`:  \nUpdate PR title/body",
            "📖": "`search_handbook`:  \nSearch Hypha's handbook",
            "📅": "`get_upcoming_holiday`:  \nFetch upcoming statutory holidays",
            "🌴": "`get_upcoming_vacations`:  \nGet information about our colleague's upcoming vacations",
            "🗄️": "`get_archive_categories`:  \nList archivable categories with links",
            "🔢": "`calc`:  \nPerform calculations",
            "🧠": "`query`:  \nSearch Hypha's handbook and public drive documents with RAG via minima MCP",
            "🌐": "`web_search`:  \nSearch the internet for current information using Claude with web search",
            "🧭": "`consensus_analyzer`:  \nAnalyzes a conversation to identify agreements, disagreements, sentiment, and provide a summary. Conclude with a list of 1-3 suggested next steps.",
            "🔮": "`analyze_meeting_notes`:  \nAnalyze Co-Creation Labs meeting notes to gather insights and answer questions"
        };
        console.log("Using fallback tool constants");
    }
}

// Load configuration (backend port, host and tool constants)
async function loadConfig() {
    // Load tool constants first
    await loadToolConstants();

    let backendPort = 8000; // Default fallback port
    let backendHost = 'localhost'; // Default fallback host

    try {
        // Try to get port and host from api_config.json file created by backend
        const configResponse = await fetch("api_config.json");
        if (configResponse.ok) {
            const apiConfig = await configResponse.json();
            backendPort = apiConfig.port;
            backendHost = apiConfig.host || 'localhost';
        } else {
            console.warn("Could not read api_config.json, status:", configResponse.status);
        }
    } catch (portError) {
        console.warn("Could not get port from file:", portError);

        // Try alternate method - check the port-info endpoint
        try {
            // Try with default port first
            const apiResponse = await fetch(`http://localhost:8000/port-info`);
            if (apiResponse.ok) {
                const portInfo = await apiResponse.json();
                backendPort = portInfo.port;
                backendHost = portInfo.host || 'localhost';
                console.log("Backend port set from API:", backendPort);
                console.log("Backend host set from API:", backendHost);
            }
        } catch (apiError) {
            console.warn("Could not get port from API, using defaults:", backendPort, backendHost);
        }
    }

    // Make backendPort and backendHost globally available
    window.backendPort = backendPort;
    window.backendHost = backendHost;
}

async function loadBranding() {
    try {
        const response = await fetch('/branding');
        if (!response.ok) return;
        const branding = await response.json();
        if (branding.colors) {
            const root = document.documentElement.style;
            const map = {
                bg: '--bg', text: '--text',
                user: '--user-color', assistant: '--assistant-color',
                summary: '--accent', link: '--link',
                linkHoverBg: '--link-hover-bg',
                linkHoverText: '--link-hover-text',
            };
            for (const [key, prop] of Object.entries(map)) {
                if (branding.colors[key]) root.setProperty(prop, branding.colors[key]);
            }
        }
        if (branding.title) document.title = branding.title;
        if (branding.logoUrl) {
            const logo = document.getElementById('brand-logo');
            if (logo) { logo.src = branding.logoUrl; logo.classList.remove('hidden'); }
        }
    } catch (e) {
        console.warn('Could not load branding:', e);
    }
}

// Initialize configuration
(async function initializeApp() {
    await loadConfig(); // Ensure backendPort is set before proceeding
    await loadBranding();

    // Generate or retrieve a session ID
    if (!window.sessionId) {
        const urlParams = new URLSearchParams(window.location.search);
        const existingSessionId = urlParams.get('session_id');

        if (existingSessionId) {
            window.sessionId = existingSessionId;
            sessionId = window.sessionId;

            // Load chat history for the session
            loadChatHistory(sessionId);
        } else {
            window.sessionId = generateUUID();
            sessionId = window.sessionId;

            // Update the URL with the session ID
            const newUrl = new URL(window.location.href);
            newUrl.searchParams.set('session_id', window.sessionId);
            window.history.replaceState(null, '', newUrl);
        }
    }
})();

let chatHistory = [];

// Function to generate a UUID
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        const r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

async function loadChatHistory(sessionId) {
    console.log("Loading chat history for session:", sessionId);
    console.log("Backend port:", window.backendPort);
    console.log("Backend host:", window.backendHost);
    try {
        const response = await fetch(`/chat-history?session_id=${sessionId}`);
        if (response.ok) {

            const result = await response.json();

            console.log("Chat history response:", result);
            if (result.status === "ok" && Array.isArray(result.history)) {
                chatHistory = result.history; // Update the global chatHistory variable

                // Render the chat history
                chatHistory.forEach(entry => {
                    addMessage(entry.content, entry.role === "user" ? "user" : "assistant");
                });
            } else {
                console.warn("Unexpected response format or empty history:", result);
            }
        } else {
            console.warn("Failed to load chat history:", response.status, response.statusText);
        }
    } catch (error) {
        console.error("Error loading chat history:", error);
    }
}

document.getElementById("submit-button").addEventListener("click", sendMessage);
document.getElementById("text-input").addEventListener("keypress", function (event) {
    if (event.key === "Enter") sendMessage();
});

document.getElementById("text-input").addEventListener("input", function () {
    this.style.height = "auto"; // Reset height
    this.style.height = (this.scrollHeight) + "px"; // Expand to fit content
});

async function sendMessage() {
    isThinking = true;

    const inputField = document.getElementById("text-input");
    const submitButton = document.getElementById("submit-button");
    const message = inputField.value.trim();
    if (!message) return;

    inputField.classList.add("hidden");
    submitButton.classList.add("hidden");

    inputField.value = "";
    addMessage(`${message}`, "user");

    chatHistory.push({ role: "user", content: message });

    const chat = document.getElementById("chat");

    // Container for bot response
    let botMessageDiv = document.createElement("div");
    botMessageDiv.classList.add("bot-message");

    let responseDiv = document.createElement("div");
    botMessageDiv.appendChild(responseDiv);
    chat.appendChild(botMessageDiv);

    // Create emoji container first so it appears above the response
    let emojiDiv = document.createElement("div");
    emojiDiv.classList.add("tool-emojis");
    responseDiv.appendChild(emojiDiv);

    // Create a container for the response content
    let responseContentDiv = document.createElement("div");
    responseDiv.appendChild(responseContentDiv);

    // Create loading indicator inside the response content div
    let loadingDiv = document.createElement("div");
    loadingDiv.classList.add("loading-indicator");
    loadingDiv.textContent = ".";  // Initial dot
    responseContentDiv.appendChild(loadingDiv);

    // Start dot animation
    let dotCount = 1;
    const loadingInterval = setInterval(() => {
        dotCount = (dotCount % 3) + 1; // cycle through 1, 2, 3
        loadingDiv.textContent = ".".repeat(dotCount);
    }, 500);

    const headers = new Headers();
    headers.append('Content-Type', 'application/json');

    try {
        const response = await fetch(`/chat`, {
            method: "POST",
            headers: headers,
            body: JSON.stringify({
                message: message,
                session_id: window.sessionId
            })
        });

        if (!response.body) {
            responseContentDiv.textContent = "Error: No response stream";
            return;
        }

        if (!response.ok) {
            console.error(`Error: ${response.status} ${response.statusText}`);
            responseContentDiv.textContent = `Error: ${response.status} ${response.statusText}`;
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");

        let fullReply = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split("\n").filter(line => line.startsWith("data:"));
            for (const line of lines) {
                try {
                    const jsonString = line.replace("data: ", "");
                    const data = JSON.parse(jsonString);

                    if (data.type === "emoji") {
                        const emojiSpan = document.createElement("span");
                        emojiSpan.textContent = data.emoji;
                        emojiSpan.addEventListener("click", function (event) {
                            showEmojiPopup(event, data.emoji);
                        });
                        emojiDiv.appendChild(emojiSpan);
                    } else if (data.type === "reply") {
                        fullReply = data.content;
                    }
                } catch (err) {
                    console.error("Error parsing chunk:", err);
                }
            }
        }

        // Render final reply
        if (fullReply) {
            // Clear the loading indicator
            loadingDiv.style.display = "none";

            addMessage(fullReply, "assistant");

            // Stop loading animation
            clearInterval(loadingInterval);

            chatHistory.push({ role: "assistant", content: fullReply });
        }

    } catch (error) {
        responseContentDiv.textContent = "Error: Unable to reach AI server";
        console.error(error);
    }

    inputField.classList.remove("hidden");
    submitButton.classList.remove("hidden");
    isThinking = false;
}


// Function to show emoji popup with markdown rendering
function showEmojiPopup(event, emoji) {
    const clickedEmoji = event.target;

    // Check if there's already a popup for this emoji
    const existingPopups = document.querySelectorAll('.emoji-popup');
    existingPopups.forEach(popup => {
        // If clicking the same emoji that has an active popup, remove it (toggle off)
        popup.remove();
    });

    // If we just removed a popup for this emoji, don't create a new one
    if (clickedEmoji.dataset.hasPopup === "true") {
        clickedEmoji.dataset.hasPopup = "false";
        return;
    }

    // Create popup element
    const popup = document.createElement('div');
    popup.classList.add('emoji-popup');

    // Get tool description from map and render as markdown
    const toolDescription = emojiToolMap[emoji] || "Unknown tool";
    popup.innerHTML = marked.parse(toolDescription, { sanitize: false });

    // Position popup near the emoji, viewport-aware
    document.body.appendChild(popup);
    const rect = clickedEmoji.getBoundingClientRect();
    const popupWidth = popup.offsetWidth;
    const left = rect.right + popupWidth > window.innerWidth
        ? Math.max(0, rect.right - popupWidth)
        : rect.left;
    popup.style.left = `${left}px`;
    popup.style.top = `${rect.bottom + 5}px`;

    // Mark this emoji as having a popup
    clickedEmoji.dataset.hasPopup = "true";

    // Close popup when clicking elsewhere
    document.addEventListener('click', function closePopup(e) {
        if (e.target !== clickedEmoji) {
            popup.remove();
            clickedEmoji.dataset.hasPopup = "false";
            document.removeEventListener('click', closePopup);
        }
    });
}

function addMessage(text, type) {
    const chat = document.getElementById("chat");
    const messageDiv = document.createElement("div");

    const userCharacter = document.createElement("span")
    userCharacter.textContent = "> ";
    userCharacter.classList.add("mr1");
    messageDiv.appendChild(userCharacter);

    // Handle <think> tags for assistant messages
    if (type === "assistant") {
        const { mainContent, thinkingContent } = extractThinkingContent(text);

        // Wrap thinking + message in a column div so label stays inline
        const contentWrapper = document.createElement("div");

        // Add thinking section first if thinking content exists
        if (thinkingContent) {
            contentWrapper.appendChild(createThinkingSection(thinkingContent));
        }

        // Add main content (without thinking tags)
        const message = document.createElement("span");
        // Configure marked to preserve HTML tags
        let html = transformSourceCitations(marked.parse(mainContent, { sanitize: false }));
        // Rewrite file:///documents/ links from LLM to /dufs/ paths
        html = html.replace(/href="file:\/\/\/documents\//g, 'href="/dufs/');
        message.innerHTML = html;
        message.querySelectorAll('a[href^="/dufs/"]').forEach(link => {
            link.addEventListener('click', e => {
                e.preventDefault();
                openFileViewer(link.href, link.textContent);
            });
        });
        contentWrapper.appendChild(message);
        messageDiv.appendChild(contentWrapper);
    } else {
        // For user messages, render normally
        const message = document.createElement("span");
        message.innerHTML = marked.parse(text, { sanitize: false });
        messageDiv.appendChild(message);
    }

    messageDiv.classList.add("message", type);

    chat.appendChild(messageDiv);
    chat.scrollTop = chat.scrollHeight;
    return messageDiv;
}

function extractThinkingContent(text) {
    // Extract content between <think> and </think> tags
    const thinkRegex = /<think>([\s\S]*?)<\/think>/gi;
    let thinkingContent = '';
    let mainContent = text;

    // Find all thinking blocks
    let match;
    const thinkingBlocks = [];
    while ((match = thinkRegex.exec(text)) !== null) {
        thinkingBlocks.push(match[1].trim());
    }

    if (thinkingBlocks.length > 0) {
        // Remove <think> tags from main content
        mainContent = text.replace(thinkRegex, '').trim();
        // Combine all thinking blocks
        thinkingContent = thinkingBlocks.join('\n\n---\n\n');
    }

    return { mainContent, thinkingContent };
}

function createThinkingSection(thinkingContent) {
    // Create a details element for native expandable functionality
    const details = document.createElement("details");
    details.classList.add("thinking-details");

    // Create summary element
    const summary = document.createElement("summary");
    summary.textContent = "Thinking process";
    summary.classList.add("thinking-summary");

    // Create thinking content div
    const thinkingContentDiv = document.createElement("div");
    thinkingContentDiv.classList.add("thinking-content");
    thinkingContentDiv.innerHTML = marked.parse(thinkingContent, { sanitize: false });

    // Assemble the details element
    details.appendChild(summary);
    details.appendChild(thinkingContentDiv);

    return details;
}

// Add event listeners for the new buttons
document.getElementById("history-button").addEventListener("click", () => {
    const isHistory = !document.getElementById("history-container").classList.contains("hidden");
    isHistory ? showView("chat") : showSessionHistory();
});
document.getElementById("new-session-button").addEventListener("click", createNewSession);
document.getElementById("files-button").addEventListener("click", toggleFileView);

function showView(view) {
    const views = {
        chat: document.getElementById("chat-container"),
        files: document.getElementById("files-container"),
        history: document.getElementById("history-container"),
    };
    for (const [name, el] of Object.entries(views)) {
        el.classList.toggle("hidden", name !== view);
    }
    document.getElementById("history-button").textContent =
        view === "history" ? "Chat" : "History";
    document.getElementById("files-button").textContent =
        view === "files" ? "Chat" : "Files";
}

function toggleFileView() {
    const filesContainer = document.getElementById("files-container");
    if (filesContainer.classList.contains("hidden")) {
        showView("files");
        const frame = document.getElementById("files-frame");
        if (!frame.src || frame.src === "about:blank") {
            frame.src = "/dufs/";
        }
    } else {
        showView("chat");
    }
}

// Function to show session history
async function showSessionHistory() {
    showView("history");
    const container = document.getElementById("history-container");
    container.innerHTML = "<p>Loading sessions...</p>";
    try {
        const response = await fetch(`/sessions`);
        if (response.ok) {
            const data = await response.json();
            const sessions = data.sessions;

            container.innerHTML = "<h3>Session History</h3>";
            sessions.forEach(session => {
                const div = document.createElement("div");
                div.classList.add("session-item");
                const prompt = document.createElement("div");
                prompt.classList.add("session-prompt");
                prompt.textContent = session.initial_prompt;
                const date = document.createElement("div");
                date.classList.add("session-date");
                date.textContent = new Date(session.created_at).toLocaleString();
                div.appendChild(prompt);
                div.appendChild(date);
                div.addEventListener("click", () => loadSession(session.id));
                container.appendChild(div);
            });
        }
    } catch (error) {
        console.error("Error fetching session history:", error);
        container.innerHTML = "<p>Error loading session history</p>";
    }
}

// Function to load a specific session
async function loadSession(sessionId) {
    showView("chat");
    window.sessionId = sessionId;

    // Update URL with new session ID
    const newUrl = new URL(window.location.href);
    newUrl.searchParams.set('session_id', sessionId);
    window.history.pushState(null, '', newUrl);

    // Clear existing chat
    const chatDiv = document.getElementById("chat");
    chatDiv.innerHTML = '';

    // Load chat history for the session
    await loadChatHistory(sessionId);
}

// Function to create a new session
async function createNewSession() {
    showView("chat");
    // Get the latest summary from the current session if it exists
    let latestSummary = "New session - no messages yet";
    if (window.sessionId) {
        try {
            const response = await fetch(`/sessions/${window.sessionId}/summary`);
            if (response.ok) {
                const data = await response.json();
                if (data.status === "ok") {
                    latestSummary = data.summary;
                }
            }
        } catch (error) {
            console.error("Error fetching latest summary:", error);
        }
    }

    // Generate new session ID
    const newSessionId = generateUUID();
    window.sessionId = newSessionId;

    // Update URL with new session ID
    const newUrl = new URL(window.location.href);
    newUrl.searchParams.set('session_id', newSessionId);
    window.history.pushState(null, '', newUrl);

    // Clear existing chat and history
    const chatDiv = document.getElementById("chat");
    chatDiv.innerHTML = '';
    chatHistory = [];

    // Add a message showing the latest summary
    if (latestSummary !== "New session - no messages yet") {
        addMessage(`Previous session summary: ${latestSummary}`, "assistant");
    }
}

function injectDufsStyles(frame) {
    try {
        const doc = frame.contentDocument;
        if (!doc || !doc.head) return;
        const style = doc.createElement('style');
        style.textContent = `
            body { background: #000 !important; color: #eee !important; }
            table, th, td { background: #000 !important; color: #eee !important; border-color: #444 !important; }
            a { color: #eee !important; }
            a:hover { background: #eee !important; color: #000 !important; }
            nav ol li:first-child { display: none !important; }
            tr:has(a[href*="lost"]) { display: none !important; }
            /* markdown rendered content */
            h1, h2, h3, h4, h5, h6 { color: #eee !important; }
            p, li, blockquote, pre, code { color: #eee !important; background: #000 !important; }
            pre, code { background: #1a1a1a !important; }
            hr { border-color: #444 !important; }
        `;
        doc.head.appendChild(style);
    } catch (e) {
        console.warn('Could not inject dufs styles:', e);
    }
}

document.getElementById('files-frame').addEventListener('load', function () {
    injectDufsStyles(this);
});

document.getElementById('file-viewer-frame').addEventListener('load', function () {
    injectDufsStyles(this);
});

function openFileViewer(url, name) {
    document.getElementById('file-viewer-name').textContent = name || url;
    document.getElementById('file-viewer-frame').src = url;
    document.getElementById('file-viewer').classList.remove('hidden');
}

document.getElementById('file-viewer-close').addEventListener('click', () => {
    document.getElementById('file-viewer').classList.add('hidden');
    document.getElementById('file-viewer-frame').src = '';
});

(function initIndexerStatus() {
    const el = document.getElementById("indexer-status");
    if (!el) return;

    function isIndexing(data) {
        if (!data) return false;
        const p = data.phase;
        return p === "starting" || p === "crawling" || p === "initial_indexing"
            || (p === "watching" && data.queue_depth > 0);
    }

    function getInterval(data) {
        if (!data || data.phase === "offline") return 30000;
        if (isIndexing(data)) return 3000;
        return 5000;
    }

    function render(data) {
        el.className = "";
        el.title = "";
        if (!data || data.phase === "offline") {
            el.textContent = "indexer offline";
            el.classList.add("status-offline");
            return;
        }
        const uptime = data.uptime_seconds != null
            ? (data.uptime_seconds < 3600
                ? `${Math.round(data.uptime_seconds / 60)}m`
                : `${Math.round(data.uptime_seconds / 3600)}h`)
            : null;
        const tooltip = [
            `phase: ${data.phase}`,
            data.files_discovered != null ? `discovered: ${data.files_discovered}` : null,
            data.files_indexed != null ? `indexed: ${data.files_indexed}` : null,
            data.files_skipped > 0 ? `skipped: ${data.files_skipped}` : null,
            data.files_failed > 0 ? `failed: ${data.files_failed}` : null,
            data.queue_depth != null ? `queue: ${data.queue_depth}` : null,
            uptime ? `uptime: ${uptime}` : null,
            data.last_file_processed
                ? `last: ${data.last_file_processed.split('/').pop()}` : null,
        ].filter(Boolean).join('\n');
        el.title = tooltip;
        if (isIndexing(data)) {
            el.textContent = `Indexing: ${data.files_processed}/${data.files_discovered} files`;
            el.classList.add("status-indexing");
            return;
        }
        if (data.file_watcher_alive === false) {
            el.textContent = "watcher down";
            el.classList.add("status-warning");
        } else if (data.files_failed > 0) {
            el.textContent = `Ready (${data.files_failed} failed)`;
            el.classList.add("status-warning");
        } else {
            el.textContent = "Ready";
            el.classList.add("status-ready");
        }
    }

    async function poll() {
        let data;
        try {
            const r = await fetch("/minima/status");
            data = r.ok ? await r.json() : { phase: "offline" };
        } catch {
            data = { phase: "offline" };
        }
        render(data);
        setTimeout(poll, getInterval(data));
    }

    el.textContent = "loading...";
    el.classList.add("status-loading");
    setTimeout(poll, 1000);
})();
