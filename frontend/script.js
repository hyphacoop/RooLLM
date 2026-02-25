let isThinking = false;
let sessionId = null;
const DEBUG_LOGS = false;

// Tool emoji mapping - loaded from shared constants
let emojiToolMap = {};

function logDebug(...args) {
    if (DEBUG_LOGS) {
        console.log(...args);
    }
}

function parseJsonSafely(text) {
    try {
        return JSON.parse(text);
    } catch {
        return null;
    }
}

function apiUrl(path) {
    const base = window.apiBase || "";
    return `${base}${path}`;
}

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
            logDebug("Loaded tool constants from shared file");
        } else {
            throw new Error(`HTTP ${response.status}`);
        }
    } catch (error) {
        logDebug("Could not load tool constants from shared file:", error);
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
        logDebug("Using fallback tool constants");
    }
}

async function probePortInfo(url) {
    try {
        const response = await fetch(url, { cache: "no-store" });
        if (!response.ok) return null;
        const text = await response.text();
        const data = parseJsonSafely(text);
        if (!data || typeof data.port !== "number") return null;
        return {
            port: data.port,
            host: data.host || "localhost"
        };
    } catch {
        return null;
    }
}

async function readApiConfigFile() {
    try {
        const response = await fetch("api_config.json", { cache: "no-store" });
        if (!response.ok) return null;

        const text = await response.text();
        const config = parseJsonSafely(text);
        if (!config) return null;

        const port = Number(config.port);
        if (!Number.isFinite(port)) return null;

        return {
            port,
            host: config.host || "localhost"
        };
    } catch {
        return null;
    }
}

// Load configuration (backend port, host and tool constants)
async function loadConfig() {
    // Load tool constants first
    await loadToolConstants();

    const browserHost = window.location.hostname || "localhost";
    const browserPort = Number(window.location.port || (window.location.protocol === "https:" ? 443 : 80));
    let backendHost = browserHost;
    let backendPort = 8081; // RooLLM default
    let resolvedApiBase = "";
    let resolvedByProbe = false;

    // 1) If frontend is served by backend, same-origin /port-info should work.
    const sameOriginInfo = await probePortInfo("/port-info");
    if (sameOriginInfo) {
        backendHost = sameOriginInfo.host || browserHost;
        backendPort = sameOriginInfo.port;
        resolvedApiBase = "";
        resolvedByProbe = true;
    } else {
        // 2) Try api_config.json generated by backend startup.
        const fileConfig = await readApiConfigFile();
        if (fileConfig) {
            backendHost = fileConfig.host || browserHost;
            backendPort = fileConfig.port;
        }

        // 3) Verify backend via explicit candidate origins.
        const candidatePorts = [backendPort, 8081, 8000].filter(
            (port, index, array) => array.indexOf(port) === index
        );

        for (const port of candidatePorts) {
            const candidateBase = `${window.location.protocol}//${backendHost}:${port}`;
            const info = await probePortInfo(`${candidateBase}/port-info`);
            if (info) {
                backendHost = info.host || backendHost;
                backendPort = info.port || port;
                resolvedApiBase = (backendHost === browserHost && backendPort === browserPort)
                    ? ""
                    : `${window.location.protocol}//${backendHost}:${backendPort}`;
                resolvedByProbe = true;
                break;
            }
        }

        if (!resolvedByProbe) {
            // Safe fallback for reverse-proxy deployments: keep API calls same-origin.
            backendHost = browserHost;
            backendPort = browserPort;
            resolvedApiBase = "";
        }
    }

    window.apiBase = resolvedApiBase;
    window.backendPort = backendPort;
    window.backendHost = backendHost;
    logDebug("API base:", window.apiBase || "(same-origin)");
}

async function loadBranding() {
    try {
        const response = await fetch(apiUrl('/branding'));
        if (!response.ok) return;
        const branding = await response.json();
        const root = document.documentElement.style;
        if (branding.colors) {
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
        if (branding.logoHeight !== undefined && branding.logoHeight !== null) {
            const rawLogoHeight = String(branding.logoHeight).trim();
            if (rawLogoHeight) {
                const normalizedLogoHeight = Number.isFinite(Number(rawLogoHeight))
                    ? rawLogoHeight + 'px'
                    : rawLogoHeight;
                root.setProperty('--brand-logo-height', normalizedLogoHeight);
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
    initIndexerStatus();

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
    try {
        const response = await fetch(apiUrl(`/chat-history?session_id=${sessionId}`));
        if (response.ok) {

            const result = await response.json();

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
        const response = await fetch(apiUrl(`/chat`), {
            method: "POST",
            headers: headers,
            body: JSON.stringify({
                message: message,
                session_id: window.sessionId
            })
        });

        if (!response.body) {
            clearInterval(loadingInterval);
            responseContentDiv.textContent = "Error: No response stream";
            return;
        }

        if (!response.ok) {
            clearInterval(loadingInterval);
            console.error(`Error: ${response.status} ${response.statusText}`);
            responseContentDiv.textContent = `Error: ${response.status} ${response.statusText}`;
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");

        let fullReply = "";
        let sseBuffer = "";
        let sawReply = false;
        let streamError = null;

        function processSseEvent(eventText) {
            const dataLines = eventText
                .split("\n")
                .filter(line => line.startsWith("data:"));
            if (!dataLines.length) return;

            const payload = dataLines
                .map(line => line.replace(/^data:\s?/, ""))
                .join("\n");

            let data;
            try {
                data = JSON.parse(payload);
            } catch (err) {
                console.error("Error parsing SSE payload:", err);
                return;
            }

            if (data.type === "emoji") {
                const emojiSpan = document.createElement("span");
                emojiSpan.textContent = data.emoji;
                emojiSpan.addEventListener("click", function (event) {
                    showEmojiPopup(event, data.emoji);
                });
                emojiDiv.appendChild(emojiSpan);
                return;
            }

            if (data.type === "reply_delta") {
                const delta = typeof data.content === "string" ? data.content : "";
                if (!delta) return;

                sawReply = true;
                fullReply += delta;
                loadingDiv.style.display = "none";
                clearInterval(loadingInterval);
                responseContentDiv.textContent = fullReply;
                return;
            }

            if (data.type === "reply_done") {
                fullReply = typeof data.content === "string" ? data.content : fullReply;
                sawReply = sawReply || !!fullReply;
                return;
            }

            if (data.type === "reply") {
                fullReply = typeof data.content === "string" ? data.content : "";
                sawReply = sawReply || !!fullReply;
                return;
            }

            if (data.type === "error") {
                streamError = typeof data.content === "string"
                    ? data.content
                    : "Error: Unable to reach AI server";
            }
        }

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            sseBuffer += decoder.decode(value, { stream: true });
            const events = sseBuffer.split("\n\n");
            sseBuffer = events.pop() || "";

            for (const eventText of events) {
                processSseEvent(eventText);
            }
        }

        // Process any trailing buffered SSE payload
        if (sseBuffer.trim()) {
            processSseEvent(sseBuffer);
        }

        clearInterval(loadingInterval);

        if (streamError) {
            responseContentDiv.textContent = streamError;
        } else if (sawReply && fullReply) {
            // Replace temporary stream container with standard assistant message rendering
            botMessageDiv.remove();
            addMessage(fullReply, "assistant");
            chatHistory.push({ role: "assistant", content: fullReply });
        } else {
            responseContentDiv.textContent = "Error: Empty response from AI server";
        }

    } catch (error) {
        clearInterval(loadingInterval);
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
        const dufsPrefix = apiUrl("/dufs/");
        html = html.replace(/href="file:\/\/\/documents\//g, `href="${dufsPrefix}`);
        message.innerHTML = html;
        message.querySelectorAll(`a[href^="${dufsPrefix}"]`).forEach(link => {
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
            frame.src = apiUrl("/dufs/");
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
        const response = await fetch(apiUrl(`/sessions`));
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
            const response = await fetch(apiUrl(`/sessions/${window.sessionId}/summary`));
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
        const cs = getComputedStyle(document.documentElement);
        const v = (name) => cs.getPropertyValue(name).trim();
        const style = doc.createElement('style');
        style.textContent = `
            body { background: ${v('--bg')} !important; color: ${v('--text')} !important; }
            table, th, td { background: ${v('--bg')} !important; color: ${v('--text')} !important; border-color: ${v('--border-dim')} !important; }
            a { color: ${v('--text')} !important; }
            a:hover { background: ${v('--link-hover-bg')} !important; color: ${v('--link-hover-text')} !important; }
            nav ol li:first-child { display: none !important; }
            tr:has(a[href*="lost"]) { display: none !important; }
            /* markdown rendered content */
            h1, h2, h3, h4, h5, h6 { color: ${v('--text')} !important; }
            p, li, blockquote, pre, code { color: ${v('--text')} !important; background: ${v('--bg')} !important; }
            pre, code { background: ${v('--surface-raised')} !important; }
            hr { border-color: ${v('--border-dim')} !important; }
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

function initIndexerStatus() {
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
            const r = await fetch(apiUrl("/minima/status"));
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
}
