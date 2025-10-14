"""
Meeting notes analyzer for Co-Creation Labs Google Docs.

Automatically detects query type and selects appropriate analysis mode:
- Search mode: Quick lookups using keyword-based chunking (1 LLM call)
- Full mode: Comprehensive analysis with multi-chunk processing (2-5 LLM calls)

Features revision-aware caching and intelligent mode detection.
"""

import os
import re
import logging
from typing import Dict, List, Tuple, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Logging
log = logging.getLogger("meeting-notes")

# Global cache (keyed by doc_id + revision)
_DOC_CACHE: Dict[Tuple[str, str], str] = {}

# Configuration
MEETING_NOTES_DOC_ID = os.getenv("MEETING_NOTES_DOC_ID", "1CzAluNoyYj9UqofB3LRMNpyt35LFuIVjwYe0P28X9dI")
MEETING_NOTES_SOURCE_URL = f"https://docs.google.com/document/d/{MEETING_NOTES_DOC_ID}"

# Tool Metadata
name = 'analyze_meeting_notes'
emoji = '🔮'
description = f'Analyze Co-Creation Labs meeting notes from Google Docs. Automatically detects query type and uses appropriate analysis mode: "search" for specific lookups (1 LLM call) or "full" for comprehensive analysis (2-5 LLM calls). Source: {MEETING_NOTES_SOURCE_URL}'
parameters = {
    'type': 'object',
    'properties': {
        'question': {
            'type': 'string',
            'description': 'The question or topic to analyze. Examples: "find one check-in question", "summarize recent discussions about X", "what decisions were made?"'
        },
        'mode': {
            'type': 'string',
            'enum': ['auto', 'search', 'full'],
            'description': 'Analysis mode: "search" for quick lookups, "full" for comprehensive analysis, "auto" to detect automatically (default)',
            'default': 'auto'
        }
    },
    'required': []
}


# ===== DOCUMENT ACCESS and CACHING =====

def get_cached_document_content(service, doc_id: str) -> Tuple[str, str]:
    """Fetch document with revision-aware caching."""
    doc = service.documents().get(documentId=doc_id).execute()
    rev = doc.get("revisionId", "unknown")

    cache_key = (doc_id, rev)
    if cache_key in _DOC_CACHE:
        log.info(f"Cache hit: doc={doc_id[:8]} rev={rev[:8]}")
        return _DOC_CACHE[cache_key], rev

    # Extract text from document
    text = read_document_content_from_doc(doc)
    _DOC_CACHE[cache_key] = text
    log.info(f"Cache miss: fetched {len(text)} chars")
    return text, rev


def read_document_content_from_doc(document: Dict) -> str:
    """Extract text from Google Doc structure."""
    content = document.get('body', {}).get('content', [])
    text_parts = []

    for element in content:
        if 'paragraph' in element:
            for text_run in element['paragraph'].get('elements', []):
                if 'textRun' in text_run:
                    text_parts.append(text_run['textRun'].get('content', ''))
        elif 'table' in element:
            # Extract tables as pipe-separated values
            table = element['table']
            for row in table.get('tableRows', []):
                cells = []
                for cell in row.get('tableCells', []):
                    cell_text = []
                    for cell_content in cell.get('content', []):
                        if 'paragraph' in cell_content:
                            for elem in cell_content['paragraph'].get('elements', []):
                                if 'textRun' in elem:
                                    cell_text.append(elem['textRun'].get('content', ''))
                    cells.append(''.join(cell_text).strip())
                text_parts.append(' | '.join(cells) + '\n')

    return ''.join(text_parts)


def get_google_docs_service(creds=None, api_key=None):
    """Create Google Docs API service."""
    if api_key:
        return build('docs', 'v1', developerKey=api_key)
    elif creds:
        return build('docs', 'v1', credentials=creds)
    else:
        raise ValueError("Either credentials or API key must be provided")


# ===== MODE DETECTION =====

def is_specific_query(question: str) -> bool:
    """
    Detect if user wants a specific lookup vs comprehensive analysis.

    Specific queries: "find", "list", "what did X say", "show me", etc.
    Analytical queries: "summarize", "analyze", "what patterns", etc.
    """
    q_lower = question.lower()

    # Specific lookup keywords
    specific_keywords = ['find', 'list', 'show', 'give me', 'what are', 'get', 'extract', 'who said']
    if any(kw in q_lower for kw in specific_keywords):
        return True

    # Check for quantity requests (numbered or word numbers)
    if re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(check-in\s+)?questions?', q_lower):
        return True
    if re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(items?|examples?|instances?)', q_lower):
        return True

    # Analytical keywords suggest comprehensive mode
    analytical_keywords = ['summarize', 'analyze', 'what patterns', 'how has', 'why', 'explain']
    if any(kw in q_lower for kw in analytical_keywords):
        return False

    # Default to specific for short questions
    return len(question.split()) < 10


# ===== CHUNK HANDLING =====

def find_relevant_chunks(full_text: str, question: str, max_chunks: int = 3, chunk_size: int = 4000) -> List[str]:
    """
    Simple keyword-based chunk finding.
    Returns the most relevant chunks based on keyword frequency.
    """
    # Extract keywords from question
    keywords = [word.strip() for word in question.lower().split() if len(word) > 3]

    # Score chunks by keyword frequency
    chunk_scores = []
    for start_pos in range(0, len(full_text), chunk_size):
        end_pos = min(start_pos + chunk_size, len(full_text))
        chunk = full_text[start_pos:end_pos]

        if not chunk.strip():
            continue

        # Count keyword occurrences
        chunk_lower = chunk.lower()
        score = sum(chunk_lower.count(kw) for kw in keywords)

        if score > 0:
            chunk_scores.append((score, chunk))

    # Return top-k chunks by score
    chunk_scores.sort(reverse=True, key=lambda x: x[0])
    return [chunk for _, chunk in chunk_scores[:max_chunks]]


def split_large_chunks(text: str, chunk_size: int = 12000) -> List[str]:
    """Split document into large chunks for comprehensive analysis."""
    chunks = []
    for start in range(0, len(text), chunk_size):
        chunk = text[start:start + chunk_size]
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def clean_text(text: str) -> str:
    """Clean up excessive whitespace while preserving structure."""
    lines = text.split('\n')
    cleaned_lines = []
    prev_empty = False

    for line in lines:
        line = line.strip()
        if not line:
            if not prev_empty:
                cleaned_lines.append('')
                prev_empty = True
        else:
            cleaned_lines.append(line)
            prev_empty = False

    return '\n'.join(cleaned_lines).strip()


# ===== MODE 1: SEARCH AND RESPOND =====

async def search_and_respond(roo, doc_text: str, question: str) -> str:
    """
    Quick lookup mode: Find relevant chunks and get direct answer.
    Single LLM call - let it do all the work!
    """
    log.info(f"Search mode: {question[:50]}")

    # Find relevant chunks
    chunks = find_relevant_chunks(doc_text, question, max_chunks=3)

    if not chunks:
        return f"❌ No relevant information found for: {question}\n\n[Source: {MEETING_NOTES_SOURCE_URL}]"

    # Clean and combine chunks
    context = "\n\n---\n\n".join([clean_text(chunk) for chunk in chunks])

    # Single LLM call with simple, clear prompt
    prompt = f"""Answer this question about Co-Creation Labs meeting notes:

**Question:** {question}

**Relevant excerpts from meeting notes:**

{context}

**Instructions:**
- Provide a clear, direct answer based on the notes above
- If looking for specific items (questions, topics, etc.), extract them verbatim
- If the notes don't contain the information, say so
- Be concise but complete"""

    messages = [{"role": "user", "content": prompt}]
    response = await roo.inference.invoke(messages=messages, tools=None)

    # Extract content
    if response and isinstance(response, dict):
        content = response.get("message", {}).get("content") or response.get("content", "")

        # Format response
        result = f"📝 **Search Results**\n\n{content}\n\n"
        result += f"[Source: {MEETING_NOTES_SOURCE_URL}]"
        return result

    return f"❌ Error: Could not process response\n\n[Source: {MEETING_NOTES_SOURCE_URL}]"


# ===== MODE 2: READ AND SYNTHESIZE =====

async def read_and_synthesize(roo, doc_text: str, question: str) -> str:
    """
    Comprehensive analysis mode: Read larger chunks and synthesize.
    2-5 LLM calls depending on document size.
    """
    log.info(f"Synthesize mode: {question[:50]}")

    # Split into large chunks
    chunks = split_large_chunks(doc_text, chunk_size=12000)

    # If document fits in one chunk, do single-pass analysis
    if len(chunks) == 1:
        return await single_pass_analysis(roo, chunks[0], question)

    # Multi-chunk: extract from each, then synthesize
    log.info(f"Processing {len(chunks)} chunks")
    findings = []

    for i, chunk in enumerate(chunks):
        prompt = f"""Read this section of Co-Creation Labs meeting notes and extract information relevant to: "{question}"

**Section {i+1} of {len(chunks)}:**

{clean_text(chunk)}

**Instructions:**
- Extract any information related to the question
- Be specific and preserve important details
- If nothing relevant, state "No relevant information in this section"
"""

        messages = [{"role": "user", "content": prompt}]
        response = await roo.inference.invoke(messages=messages, tools=None)

        if response and isinstance(response, dict):
            content = response.get("message", {}).get("content") or response.get("content", "")
            findings.append((i+1, content))

    # Filter out empty findings
    relevant_findings = [(num, finding) for num, finding in findings
                         if "no relevant information" not in finding.lower()]

    if not relevant_findings:
        return f"❌ No relevant information found for: {question}\n\n[Source: {MEETING_NOTES_SOURCE_URL}]"

    # Final synthesis
    combined = "\n\n".join([f"**From Section {num}:**\n{finding}"
                           for num, finding in relevant_findings])

    final_prompt = f"""Based on these findings from Co-Creation Labs meeting notes, provide a comprehensive answer to: "{question}"

**Findings from document:**

{combined}

**Instructions:**
- Synthesize the information into a clear, well-structured answer
- Identify patterns or themes if relevant
- Highlight key insights
- Be comprehensive but concise
"""

    messages = [{"role": "user", "content": final_prompt}]
    response = await roo.inference.invoke(messages=messages, tools=None)

    if response and isinstance(response, dict):
        content = response.get("message", {}).get("content") or response.get("content", "")

        result = f"📝 **Comprehensive Analysis**\n\n{content}\n\n"
        result += f"_Analyzed {len(relevant_findings)} sections of the document_\n"
        result += f"[Source: {MEETING_NOTES_SOURCE_URL}]"
        return result

    return f"❌ Error: Could not synthesize findings\n\n[Source: {MEETING_NOTES_SOURCE_URL}]"


async def single_pass_analysis(roo, doc_text: str, question: str) -> str:
    """Single LLM call for documents that fit in one chunk."""
    prompt = f"""Analyze these Co-Creation Labs meeting notes and answer: "{question}"

**Meeting Notes:**

{clean_text(doc_text)}

**Instructions:**
- Provide a comprehensive, well-structured answer
- Include relevant details and context
- Identify patterns or themes if applicable
"""

    messages = [{"role": "user", "content": prompt}]
    response = await roo.inference.invoke(messages=messages, tools=None)

    if response and isinstance(response, dict):
        content = response.get("message", {}).get("content") or response.get("content", "")

        result = f"📝 **Analysis**\n\n{content}\n\n"
        result += f"[Source: {MEETING_NOTES_SOURCE_URL}]"
        return result

    return f"❌ Error: Could not analyze document\n\n[Source: {MEETING_NOTES_SOURCE_URL}]"


# ===== MAIN TOOL FUNCTION =====

async def tool(roo, arguments: dict, user: str):
    """
    Simplified meeting notes analyzer.

    Automatically selects between:
    - Search mode: Quick lookups (1 LLM call)
    - Synthesize mode: Comprehensive analysis (2-5 LLM calls)
    """
    # Setup Google Docs auth
    api_key = roo.config.get("google_docs_api_key")
    creds = None

    if not api_key:
        creds_dict = roo.config.get("google_docs_creds") or roo.config.get("google_creds")
        if not creds_dict:
            return "❌ Error: Google Docs access not configured. Please add GOOGLE_DOCS_API_KEY or GOOGLE_DOCS_CREDENTIALS to your .env file."

        log.info(f"Using service account: {creds_dict.get('client_email', 'UNKNOWN')}")

        scopes = [
            'https://www.googleapis.com/auth/documents.readonly',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)

        # Refresh credentials
        try:
            from google.auth.transport.requests import Request as GoogleRequest
            creds.refresh(GoogleRequest())
            log.info("Credentials refreshed")
        except Exception as e:
            log.warning(f"Could not refresh credentials: {e}")

    # Get question and mode
    question = arguments.get("question", "Provide a summary of the most recent discussions and key decisions")
    mode = arguments.get("mode", "auto")

    try:
        # Get document (cached)
        service = get_google_docs_service(creds=creds, api_key=api_key)
        doc_text, revision = get_cached_document_content(service, MEETING_NOTES_DOC_ID)

        if not doc_text:
            return f"❌ Error: Could not read document or document is empty.\n\n[Source: {MEETING_NOTES_SOURCE_URL}]"

        log.info(f"Document loaded: {len(doc_text)} chars, rev={revision[:8]}")

        # Auto-detect mode if needed
        if mode == "auto":
            mode = "search" if is_specific_query(question) else "full"
            log.info(f"Auto-detected mode: {mode}")

        # Execute appropriate mode
        if mode == "search":
            return await search_and_respond(roo, doc_text, question)
        else:  # mode == "full"
            return await read_and_synthesize(roo, doc_text, question)

    except Exception as e:
        log.error(f"Error analyzing meeting notes: {e}", exc_info=True)
        return f"❌ Error analyzing meeting notes: {str(e)}\n\n[Source: {MEETING_NOTES_SOURCE_URL}]"
