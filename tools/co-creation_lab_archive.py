"""
Co-Creation Labs archive analyzer for Google Docs.

Automatically detects query type and selects appropriate analysis mode:
- Search mode: Quick lookups using keyword-based chunking (1 LLM call)
- Full mode: Comprehensive analysis with multi-chunk processing (2-5 LLM calls)

Features revision-aware caching and intelligent mode detection.
"""

import os
import re
import logging
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Logging
log = logging.getLogger("co-creation-lab-archive")

# Global cache (keyed by doc_id + revision)
_DOC_CACHE: Dict[Tuple[str, str], str] = {}

# Configuration
MEETING_NOTES_DOC_ID = os.getenv("MEETING_NOTES_DOC_ID", "1CzAluNoyYj9UqofB3LRMNpyt35LFuIVjwYe0P28X9dI")
MEETING_NOTES_SOURCE_URL = f"https://docs.google.com/document/d/{MEETING_NOTES_DOC_ID}"

# Tool Metadata
name = 'co_creation_lab_archive'
emoji = '🔮'
description = f'Search the Co-Creation Lab archive (Google Doc with check-in questions and meeting notes). Automatically detects query type and uses appropriate analysis mode: "search" for specific lookups (1 LLM call) or "full" for comprehensive analysis (2-5 LLM calls). Source: {MEETING_NOTES_SOURCE_URL}'
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
        log.debug(f"Cache hit: doc={doc_id[:8]} rev={rev[:8]}")
        return _DOC_CACHE[cache_key], rev

    # Extract text from document
    text = read_document_content_from_doc(doc)

    _DOC_CACHE[cache_key] = text
    log.debug(f"Cache miss: fetched {len(text)} chars")
    return text, rev


def extract_date_from_calendar_uri(uri: str) -> Optional[str]:
    """
    Extract and format date from Google Calendar URI.
    Example URI: https://www.google.com/calendar/event?eid=...base64...
    The eid parameter contains base64-encoded data with the date.
    Returns formatted date like "Sep 2, 2025"

    Note: Calendar times are in UTC, so we convert to local timezone to match what
    users see in the Google Docs interface. Timezone can be configured via
    MEETING_NOTES_TIMEZONE environment variable (e.g., "America/Toronto", "Asia/Tokyo").
    Defaults to system local timezone if not set.
    """
    import re
    import base64
    from urllib.parse import urlparse, parse_qs
    from datetime import timezone

    # Get timezone from environment or use system local timezone
    tz_name = os.getenv("MEETING_NOTES_TIMEZONE")

    try:
        from zoneinfo import ZoneInfo
        if tz_name:
            try:
                LOCAL_TZ = ZoneInfo(tz_name)
                log.debug(f"Using timezone from env: {tz_name}")
            except Exception as e:
                log.warning(f"Invalid timezone '{tz_name}': {e}, falling back to system local timezone")
                LOCAL_TZ = None  # Will use system default
        else:
            # Use system local timezone
            LOCAL_TZ = None  # datetime.astimezone() with None uses local timezone
            log.debug("Using system local timezone")
    except ImportError:
        # Fallback for Python < 3.9 or systems without zoneinfo
        try:
            import pytz
            if tz_name:
                LOCAL_TZ = pytz.timezone(tz_name)
                log.debug(f"Using timezone from env (pytz): {tz_name}")
            else:
                # Default to America/Toronto as a reasonable guess
                LOCAL_TZ = pytz.timezone("America/Toronto")
                log.debug("Using default timezone: America/Toronto (pytz)")
        except ImportError:
            # Last resort: use a fixed offset (EDT = UTC-4)
            from datetime import timedelta
            log.warning("Neither zoneinfo nor pytz available, using fixed UTC-4 offset")
            LOCAL_TZ = timezone(timedelta(hours=-4))

    try:
        # Parse the URI and extract the eid parameter
        parsed = urlparse(uri)
        params = parse_qs(parsed.query)
        eid = params.get('eid', [None])[0]

        if eid:
            # Base64 decode the eid (add padding if needed)
            padding_needed = (4 - len(eid) % 4) % 4
            if padding_needed:
                eid += '=' * padding_needed
            decoded = base64.b64decode(eid).decode('utf-8', errors='ignore')

            # Look for YYYYMMDDTHHMMSSZ pattern in decoded string
            match = re.search(r'(\d{8})T(\d{6})Z', decoded)
            if match:
                date_str = match.group(1)  # YYYYMMDD
                time_str = match.group(2)  # HHMMSS

                year = int(date_str[0:4])
                month = int(date_str[4:6])
                day = int(date_str[6:8])
                hour = int(time_str[0:2])
                minute = int(time_str[2:4])
                second = int(time_str[4:6])

                # Create datetime in UTC
                dt_utc = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)

                # Convert to local timezone (handles DST automatically)
                if LOCAL_TZ is None:
                    # Use system local timezone
                    dt_local = dt_utc.astimezone()
                else:
                    dt_local = dt_utc.astimezone(LOCAL_TZ)

                formatted_date = dt_local.strftime("%b %#d, %Y" if os.name == 'nt' else "%b %-d, %Y")
                log.debug(f"Calendar date conversion: {dt_utc} UTC -> {dt_local} local -> '{formatted_date}'")
                return formatted_date

            # Also try to find other date patterns in the decoded string
            # Sometimes the format might be different
            alt_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', decoded)
            if alt_match:
                year, month, day = map(int, alt_match.groups())
                dt = datetime(year, month, day)
                return dt.strftime("%b %#d, %Y" if os.name == 'nt' else "%b %-d, %Y")

    except Exception as e:
        log.debug(f"Error extracting date from calendar URI: {e}")

    return None


def read_document_content_from_doc(document: Dict) -> str:
    """Extract text from Google Doc structure."""
    content = document.get('body', {}).get('content', [])
    text_parts = []

    for element in content:
        if 'paragraph' in element:
            for text_run in element['paragraph'].get('elements', []):
                if 'textRun' in text_run:
                    text_parts.append(text_run['textRun'].get('content', ''))
                elif 'richLink' in text_run:
                    # Extract title and potentially date from richLink (e.g., meeting titles)
                    props = text_run['richLink'].get('richLinkProperties', {})
                    title = props.get('title', '')
                    uri = props.get('uri', '')

                    # Try to extract date from calendar URI to replace the date chip (\ue907)
                    date_str = extract_date_from_calendar_uri(uri) if uri and 'calendar' in uri else None

                    if date_str and title:
                        text_parts.append(f"{date_str} | {title}")
                    elif title:
                        text_parts.append(title)
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
    Optimized to prefer search mode for faster responses.
    """
    q_lower = question.lower()

    # Specific lookup keywords (expanded list)
    specific_keywords = ['find', 'list', 'show', 'give me', 'what are', 'get', 'extract', 'who said', 
                        'what was', 'what is', 'when', 'where', 'which', 'check-in', 'question']
    if any(kw in q_lower for kw in specific_keywords):
        return True

    # Check for quantity requests (numbered or word numbers)
    if re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(check-in\s+)?questions?', q_lower):
        return True
    if re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(items?|examples?|instances?)', q_lower):
        return True

    # If the question contains a date-like expression, treat as specific
    if extract_date_variants(q_lower):
        return True

    # Only use comprehensive mode for clearly analytical queries
    analytical_keywords = ['summarize', 'analyze', 'what patterns', 'how has', 'why', 'explain', 'compare', 'trends']
    if any(kw in q_lower for kw in analytical_keywords):
        return False

    # Default to specific (search mode) for most questions - faster!
    return True


# ===== CHUNK HANDLING =====

def find_relevant_chunks(full_text: str, question: str, max_chunks: int = 3, chunk_size: int = 4000) -> List[str]:
    """
    Simple keyword-based chunk finding.
    Returns the most relevant chunks based on keyword frequency.
    """
    # Extract keywords from question
    q_lower = question.lower()

    # Date variants to prioritize exact meeting occurrences
    date_variants = extract_date_variants(q_lower)

    # Include domain-specific short tokens and month abbreviations
    domain_tokens = set()
    if 'check-in' in q_lower or 'check in' in q_lower:
        domain_tokens.update(['check-in', 'check in', 'checkin'])

    month_abbr = {'jan','feb','mar','apr','may','jun','jul','aug','sep','sept','oct','nov','dec'}

    words = [w.strip(".,!?()[]{}:") for w in q_lower.split()]
    keywords: List[str] = []
    for w in words:
        if len(w) > 3:
            keywords.append(w)
        elif w in month_abbr:
            keywords.append(w)
    keywords.extend(list(domain_tokens))

    # Score chunks by keyword frequency
    chunk_scores = []
    for start_pos in range(0, len(full_text), chunk_size):
        end_pos = min(start_pos + chunk_size, len(full_text))
        chunk = full_text[start_pos:end_pos]

        if not chunk.strip():
            continue

        # Count keyword occurrences
        chunk_lower = chunk.lower()
        score = 0

        # Strongly weight date matches if present
        if date_variants:
            date_hits = sum(chunk_lower.count(variant) for variant in date_variants)
            # Weight dates very high to pull in the exact meeting section
            score += date_hits * 50
            # DEBUG: Log date matching
            if date_hits > 0:
                log.debug(f"Chunk at pos {start_pos} has {date_hits} date hits, score={score}")
                # Log which variants matched
                matched_variants = [v for v in date_variants if v in chunk_lower]
                log.debug(f"Matched variants: {matched_variants[:3]}")

        # Weight domain tokens like check-in slightly higher
        for kw in keywords:
            weight = 2 if kw in domain_tokens else 1
            score += weight * chunk_lower.count(kw)

        if score > 0:
            chunk_scores.append((score, chunk))

    # Sort and log top chunks for debugging
    chunk_scores.sort(reverse=True, key=lambda x: x[0])
    if date_variants:
        log.debug(f"Date variants being searched: {date_variants[:5]}")
    top_scores = [score for score, _ in chunk_scores[:max_chunks]]
    log.debug(f"Top chunk scores (first {max_chunks}): {top_scores}")

    # Return top-k chunks by score
    top_chunks = chunk_scores[:max_chunks]
    for idx, (score, chunk) in enumerate(top_chunks):
        snippet = clean_text(chunk[:200]).replace('\n', ' ')
        log.debug(f"Chunk #{idx+1} score={score} snippet=\"{snippet[:120]}\"")
    return [chunk for _, chunk in top_chunks]


def extract_date_variants(text: str) -> List[str]:
    """
    Extract date-like expressions from text and return a list of
    normalized variants to match against the document.
    
    Also includes timezone-aware variants (day before/after) to handle
    calendar timezone conversion issues.

    Supports inputs like:
    - "Sep 2 2025", "Sept 2, 2025", "September 2, 2025"
    - "Sep 2" (no year)
    - "2025-09-02", "09/02/2025", "2025/09/02"
    Returns lowercase variants for matching.
    """
    months = {
        'jan': 1, 'january': 1,
        'feb': 2, 'february': 2,
        'mar': 3, 'march': 3,
        'apr': 4, 'april': 4,
        'may': 5,
        'jun': 6, 'june': 6,
        'jul': 7, 'july': 7,
        'aug': 8, 'august': 8,
        'sep': 9, 'sept': 9, 'september': 9,
        'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'dec': 12, 'december': 12,
    }

    variants: Set[str] = set()
    partial_variants: Set[str] = set()

    # Helper to add common textual/numeric variants
    def add_variants(year: int, month: int, day: int):
        try:
            dt = datetime(year, month, day)
        except ValueError:
            return
        y = f"{dt.year:04d}"
        m = f"{dt.month:02d}"
        d = f"{dt.day:02d}"

        # ISO and slashed
        variants.update({
            f"{y}-{m}-{d}",
            f"{m}/{d}/{y}",
            f"{y}/{m}/{d}",
        })

        # Month text variants (with and without comma)
        month_names = [
            dt.strftime('%b').lower(),  # Sep
            (dt.strftime('%b') + 't').lower() if dt.strftime('%b').lower() == 'sep' else dt.strftime('%b').lower(),  # Sept
            dt.strftime('%B').lower(),  # September
        ]
        day_no_suffix = str(dt.day)
        day_suffix = day_no_suffix + suffix_for_day(dt.day)
        for mn in month_names:
            variants.add(f"{mn} {day_no_suffix} {y}")
            variants.add(f"{mn} {day_no_suffix}, {y}")
            variants.add(f"{mn} {day_suffix} {y}")
            variants.add(f"{mn} {day_suffix}, {y}")
            variants.add(f"{y} {mn} {day_no_suffix}")

    def add_partial_variants(month: int, day: int):
        """Add month/day variants for queries without a year."""
        try:
            dt = datetime(2000, month, day)
        except ValueError:
            return

        month_names = [
            dt.strftime('%b').lower(),
            (dt.strftime('%b') + 't').lower() if dt.strftime('%b').lower() == 'sep' else dt.strftime('%b').lower(),
            dt.strftime('%B').lower(),
        ]
        day_no_suffix = str(day)
        day_suffix = day_no_suffix + suffix_for_day(day)
        for mn in month_names:
            partial_variants.add(f"{mn} {day_no_suffix}")
            partial_variants.add(f"{mn} {day_suffix}")
            partial_variants.add(f"{day_no_suffix} {mn}")
            partial_variants.add(f"{day_suffix} {mn}")
            partial_variants.add(f"{mn} {day_no_suffix},")

    # 1) Text month formats (e.g., Sep 2 2025, September 2, 2025, or Sep 2)
    month_regex = r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+([0-9]{1,2})(?:st|nd|rd|th)?(?:,)?(?:\s+([0-9]{4}))?\b"
    for m, d, y in re.findall(month_regex, text, flags=re.IGNORECASE):
        month_num = months.get(m.lower(), None)
        if month_num:
            if y:
                add_variants(int(y), int(month_num), int(d))
            else:
                # When no year specified, add partial variants AND variants with current year
                add_partial_variants(int(month_num), int(d))
                add_variants(datetime.now().year, int(month_num), int(d))

    # 2) ISO format (2025-09-02)
    for y, m, d in re.findall(r"\b(\d{4})-(\d{2})-(\d{2})\b", text):
        add_variants(int(y), int(m), int(d))

    # 3) Slash formats (09/02/2025 or 2025/09/02). Assume MM/DD/YYYY when first is <= 12
    for a, b, c in re.findall(r"\b(\d{4}|\d{2})/(\d{2})/(\d{4}|\d{2})\b", text):
        if len(a) == 4:  # YYYY/MM/DD
            y, m, d = int(a), int(b), int(c)
        elif len(c) == 4:  # MM/DD/YYYY
            m, d, y = int(a), int(b), int(c)
        else:
            continue
        add_variants(int(y), int(m), int(d))

    # 4) Slash formats without year (MM/DD)
    for m, d in re.findall(r"\b(\d{1,2})/(\d{1,2})(?!/\d)", text):
        add_partial_variants(int(m), int(d))

    all_variants = {v.lower() for v in variants}
    all_variants.update(v.lower() for v in partial_variants)
    
    # Add timezone-aware variants (day before/after) to handle calendar conversion issues
    timezone_variants = set()
    
    # Extract dates from the original text and add adjacent dates
    month_regex = r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+([0-9]{1,2})(?:st|nd|rd|th)?(?:,)?(?:\s+([0-9]{4}))?\b"
    for m, d, y in re.findall(month_regex, text, flags=re.IGNORECASE):
        month_num = months.get(m.lower(), None)
        if month_num:
            # Use provided year or assume current year for timezone variants
            year = int(y) if y else datetime.now().year
            try:
                dt = datetime(year, int(month_num), int(d))
                
                # Add day before and after
                from datetime import timedelta
                day_before = dt - timedelta(days=1)
                day_after = dt + timedelta(days=1)
                
                # Add variants for adjacent days
                for adj_date in [day_before, day_after]:
                    timezone_variants.add(adj_date.strftime("%b %-d, %Y").lower())
                    timezone_variants.add(adj_date.strftime("%b %#d, %Y").lower())  # Windows format
                    
            except ValueError:
                pass
    
    all_variants.update(timezone_variants)
    return list(all_variants)


def suffix_for_day(day: int) -> str:
    if 11 <= day % 100 <= 13:
        return 'th'
    return {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')


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
    Optimized search mode: Smart chunk finding + single LLM call.
    Uses larger, more relevant chunks to reduce processing time.
    """
    log.debug(f"Search mode: {question[:50]}")

    # Find relevant chunks with optimal size for focused context
    chunks = find_relevant_chunks(doc_text, question, max_chunks=2, chunk_size=3000)

    if not chunks:
        return f"❌ No relevant information found for: {question}\n\n[Source: {MEETING_NOTES_SOURCE_URL}]"

    # Clean and combine chunks
    context = "\n\n---\n\n".join([clean_text(chunk) for chunk in chunks])

    # Single LLM call with optimized prompt
    prompt = f"""Find the answer to this question in the Co-Creation Labs meeting notes:

**Question:** {question}

**Meeting Notes:**
{context}

**Instructions:**
- Answer directly and concisely
- IMPORTANT: The notes contain multiple meetings. You MUST find the meeting that matches the EXACT date mentioned in the question
- Look for date headers like "Sep 2, 2025 | C-Lab Weekly" or similar patterns
- Once you find the correct date, look for the check-in question ONLY in that meeting's section
- For check-in questions, quote them exactly as they appear (e.g., "Check-in question: [exact text]")
- Look for patterns like "Check-in question:", "Check in question:", "Check in:", or similar
- If not found, state "No information found for [date/topic]"
- Keep response under 100 words unless detailed analysis is needed"""

    messages = [{"role": "user", "content": prompt}]
    response = await roo.inference.invoke(messages=messages, tools=None)

    # Extract content
    if response and isinstance(response, dict):
        content = response.get("message", {}).get("content") or response.get("content", "")

        # Format response
        result = f"📝 **{content}**\n\n"
        result += f"[Source: {MEETING_NOTES_SOURCE_URL}]"
        return result

    return f"❌ Error: Could not process response\n\n[Source: {MEETING_NOTES_SOURCE_URL}]"


# ===== MODE 2: READ AND SYNTHESIZE =====

async def read_and_synthesize(roo, doc_text: str, question: str) -> str:
    """
    Comprehensive analysis mode: Read larger chunks and synthesize.
    2-5 LLM calls depending on document size.
    """
    log.debug(f"Synthesize mode: {question[:50]}")

    # Split into large chunks
    chunks = split_large_chunks(doc_text, chunk_size=12000)

    # If document fits in one chunk, do single-pass analysis
    if len(chunks) == 1:
        return await single_pass_analysis(roo, chunks[0], question)

    # Multi-chunk: extract from each, then synthesize
    log.debug(f"Processing {len(chunks)} chunks")
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

        log.debug(f"Using service account: {creds_dict.get('client_email', 'UNKNOWN')}")

        scopes = [
            'https://www.googleapis.com/auth/documents.readonly',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)

        # Refresh credentials
        try:
            from google.auth.transport.requests import Request as GoogleRequest
            creds.refresh(GoogleRequest())
            log.debug("Credentials refreshed")
        except Exception as e:
            log.warning(f"Could not refresh credentials: {e}")

    # Get question and mode
    question = arguments.get("question", "Provide a summary of the most recent discussions and key decisions")
    mode = arguments.get("mode", "auto")

    try:
        # Get document (cached)
        service = get_google_docs_service(creds=creds, api_key=api_key)
        doc_text, revision = get_cached_document_content(service, MEETING_NOTES_DOC_ID)
        log.debug(f"Getting cached document content")
        
        if not doc_text:
            return f"❌ Error: Could not read document or document is empty.\n\n[Source: {MEETING_NOTES_SOURCE_URL}]"

        log.debug(f"Document loaded: {len(doc_text)} chars, rev={revision[:8]}")

        # Auto-detect mode if needed
        if mode == "auto":
            mode = "search" if is_specific_query(question) else "full"
            log.debug(f"Auto-detected mode: {mode}")

        # Execute appropriate mode
        if mode == "search":
            return await search_and_respond(roo, doc_text, question)
        else:  # mode == "full"
            return await read_and_synthesize(roo, doc_text, question)

    except Exception as e:
        log.error(f"Error analyzing meeting notes: {e}", exc_info=True)
        return f"❌ Error analyzing meeting notes: {str(e)}\n\n[Source: {MEETING_NOTES_SOURCE_URL}]"
