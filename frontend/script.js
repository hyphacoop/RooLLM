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
 
// Load configuration (backend port and tool constants)
async function loadConfig() {
    // Load tool constants first
    await loadToolConstants();
    
    let backendPort = 8000; // Default fallback port

    try {
        // Try to get port from port.json file created by backend
        const portResponse = await fetch("port.json");
        if (portResponse.ok) {
            const portInfo = await portResponse.json();
            backendPort = portInfo.port;
        } else {
            console.warn("Could not read port.json, status:", portResponse.status);
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
                console.log("Backend port set from API:", backendPort);
            }
        } catch (apiError) {
            console.warn("Could not get port from API, using default:", backendPort);
        }
    }

    // Make backendPort globally available
    window.backendPort = backendPort;
}

// Initialize configuration
(async function initializeApp() {
    await loadConfig(); // Ensure backendPort is set before proceeding

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
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

async function loadChatHistory(sessionId) {
    console.log("Loading chat history for session:", sessionId);
    console.log("Backend port:", backendPort);
    try {
        const response = await fetch(`http://localhost:${backendPort}/chat-history?session_id=${sessionId}`);
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
document.getElementById("text-input").addEventListener("keypress", function(event) {
    if (event.key === "Enter") sendMessage();
});

document.getElementById("text-input").addEventListener("input", function() {
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
        const response = await fetch(`http://localhost:${backendPort}/chat`, {
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
                        emojiSpan.addEventListener("click", function(event) {
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
     popup.innerHTML = marked.parse(toolDescription);
     
     // Position popup near the emoji
     document.body.appendChild(popup);
     const rect = clickedEmoji.getBoundingClientRect();
     popup.style.left = `${rect.left}px`;
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
        
        // Add main content (without thinking tags)
        const message = document.createElement("span");
        message.innerHTML = marked.parse(mainContent);
        messageDiv.appendChild(message);
        
        // Add thinking section if thinking content exists
        if (thinkingContent) {
            const thinkingSection = createThinkingSection(thinkingContent);
            messageDiv.appendChild(thinkingSection);
        }
    } else {
        // For user messages, render normally
        const message = document.createElement("span");
        message.innerHTML = marked.parse(text);
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
    summary.textContent = "🧠 Thinking process";
    summary.classList.add("thinking-summary");
    
    // Create thinking content div
    const thinkingContentDiv = document.createElement("div");
    thinkingContentDiv.classList.add("thinking-content");
    thinkingContentDiv.innerHTML = marked.parse(thinkingContent);
    
    // Assemble the details element
    details.appendChild(summary);
    details.appendChild(thinkingContentDiv);
    
    return details;
}

// Add event listeners for the new buttons
document.getElementById("history-button").addEventListener("click", showSessionHistory);
document.getElementById("new-session-button").addEventListener("click", createNewSession);

// Function to show session history
async function showSessionHistory() {
    try {
        const response = await fetch(`http://localhost:${backendPort}/sessions`);
        if (response.ok) {
            const data = await response.json();
            const sessions = data.sessions;  // Get the sessions array from the response
            
            // Clear existing chat
            const chatDiv = document.getElementById("chat");
            chatDiv.innerHTML = '';
            
            // Display sessions as messages
            addMessage("Session History:", "assistant");
            sessions.forEach(session => {
                const sessionInfo = `Initial prompt: ${session.initial_prompt}\nSession ID: ${session.id}\nCreated: ${new Date(session.created_at).toLocaleString()}`;
                addMessage(sessionInfo, "assistant");
            });
            
            // Add a note about clicking session IDs
            addMessage("Click a session to load it", "assistant");
            
            // Make session messages clickable
            document.querySelectorAll('.assistant').forEach(div => {
                if (div.textContent.includes('Session ID:')) {
                    const sessionId = div.textContent.split('Session ID: ')[1].split('\n')[0];
                    div.style.cursor = 'pointer';
                    div.addEventListener('click', () => loadSession(sessionId));
                }
            });
        }
    } catch (error) {
        console.error("Error fetching session history:", error);
        addMessage("Error loading session history", "assistant");
    }
}

// Function to load a specific session
async function loadSession(sessionId) {
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
    // Get the latest summary from the current session if it exists
    let latestSummary = "New session - no messages yet";
    if (window.sessionId) {
        try {
            const response = await fetch(`http://localhost:${backendPort}/sessions/${window.sessionId}/summary`);
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
