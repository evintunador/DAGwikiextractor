# -*- coding: utf-8 -*-

# =============================================================================
#  Copyright (c) 2020. Giuseppe Attardi (attardi@di.unipi.it).
# =============================================================================
#  This file is part of Tanl.
#
#  Tanl is free software; you can redistribute it and/or modify it
#  under the terms of the GNU Affero General Public License, version 3,
#  as published by the Free Software Foundation.
#
#  Tanl is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
# =============================================================================

import re
import html
from urllib.parse import quote as urlencode

# ======================================================================
# Main Processing Pipeline
# ======================================================================

def process_wikitext(text):
    """
    The main pipeline for processing raw wikitext into clean Markdown.
    Each step is a separate function for clarity and maintainability.
    """
    # Pre-processing
    text = html.unescape(text)
    text = fix_math_tags(text)
    text = rescue_number_templates(text)

    # The order of these operations is important.
    text = remove_comments(text)
    text = remove_templates(text)
    text = remove_wikitables(text)
    text = remove_reference_tags(text)
    text = remove_external_links(text)
    text = convert_internal_links(text)
    text = convert_bold_and_italics(text)
    
    text = fix_indented_math(text)
    text = format_sections_and_whitespace(text)
    return text

# ======================================================================
# Individual Cleaning Steps
# ======================================================================

def fix_math_tags(text):
    """Converts <math>...</math> to $$...$$."""
    return re.sub(r'<math.*?>(.*?)</math>', r'$$\1$$', text, flags=re.DOTALL)

def rescue_number_templates(text):
    """
    Preserves content of specific numeric templates before they are removed.
    e.g. {{val|0.999...}} -> 0.999...
    """
    # Handle {{val|...}} - often used for numbers with uncertainty or units
    # We capture the first argument.
    text = re.sub(r'\{\{val\|([^|}]+).*?\}\}', r'\1', text, flags=re.IGNORECASE)
    
    # Handle {{overline|...}} - used for repeating decimals
    text = re.sub(r'\{\{overline\|(.*?)\}\}', r'\1', text, flags=re.IGNORECASE)
    
    return text

def fix_indented_math(text):
    """
    Converts lines starting with a space that look like math to $$...$$
    """
    lines = text.split('\n')
    new_lines = []
    for line in lines:
        # Check if line starts with space and has some math-like content
        # Heuristic: starts with space, contains = or + or - or \ or numbers
        # And is not a list item (* or -)
        # Also check for common math symbols including unescaped entities
        if line.startswith(' ') and not line.strip().startswith(('*', '-', '#')):
            stripped = line.strip()
            # Basic check for math symbols: =, +, − (unicode), \, ×, ÷
            if any(x in stripped for x in ['=', '+', '−', '\\', '×', '÷']):
                 new_lines.append(f"$${stripped}$$")
                 continue
        new_lines.append(line)
    return '\n'.join(new_lines)

def remove_comments(text):
    """Removes HTML-style comments."""
    return re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

def remove_templates(text):
    """Removes template invocations (e.g., {{...}})."""
    return drop_nested(text, r'{{', r'}}')

def remove_wikitables(text):
    """Removes wikitable syntax ({|...|})."""
    return drop_nested(text, r'{\|', r'\|}')

def remove_reference_tags(text):
    """Removes reference tags (e.g. <ref>...</ref>, <ref name="..."/>)."""
    return re.sub(r'<ref.*?>.*?</ref>|<ref.*?>', '', text, flags=re.DOTALL)

def remove_external_links(text):
    """
    Removes external links, keeping the anchor text if present.
    e.g., "[http://example.com link text]" -> "link text"
    """
    text = re.sub(r'\[https?://[^ ]+\s+(.*?)\]', r'\1', text)
    return re.sub(r'\[https?://[^ ]+\]', '', text)

def convert_internal_links(text):
    """
    Replaces internal links: [[link|text]] -> [text](link)
    """
    cur = 0
    res = ''
    # match tail after wikilink, e.g. the 's' in [[apple]]s
    tail_re = re.compile(r'\w+')
    
    for s, e in find_balanced(text, ['[['], [']]']):
        m = tail_re.match(text, e)
        trail = m.group(0) if m else ''
        end = m.end() if m else e
        
        inner = text[s + 2:e - 2]
        pipe = inner.rfind('|')
        
        title = inner[:pipe].rstrip() if pipe > -1 else inner
        label = inner[pipe + 1:].strip() if pipe > -1 else title

        # Handle wikt: prefix
        if title.lower().startswith('wikt:'):
            title = title[5:]
            if pipe == -1:
                label = title

        if any(title.lower().startswith(p) for p in ['file:', 'image:', 'category:', 'media:']):
            res += text[cur:s] # Keep the original text if it's a file/image link
        else:
            encoded_title = normalize_title(title)
            res += f"{text[cur:s]}[{label}]({encoded_title}){trail}"
            
        cur = end
        
    return res + text[cur:]

def normalize_title(title):
    """
    Normalizes a title for use in filenames and link targets.
    Strict normalization to ensure alignment:
    - Lowercase
    - Replace spaces and special characters with underscores
    - Limit length
    """
    # Decode HTML entities
    title = html.unescape(title)
    # Lowercase
    title = title.lower()
    # Replace spaces with underscores
    title = title.replace(' ', '_')
    # Replace invalid chars with underscores (keep only alphanumeric, hyphen, underscore)
    title = re.sub(r'[^a-z0-9\-_]', '_', title)
    # Collapse underscores
    title = re.sub(r'__+', '_', title)
    # Strip leading/trailing underscores
    title = title.strip('_')
    # Limit length
    if len(title) > 200:
        title = title[:200]
    return title

def convert_bold_and_italics(text):
    """Converts wikitext bold/italics to Markdown."""
    text = re.sub(r"'''(.*?)'''", r'**\1**', text) # Bold
    return re.sub(r"''(.*?)''", r'*\1*', text)   # Italics

def format_sections_and_whitespace(text):
    """
    Removes unwanted sections, handles section headers, cleans up whitespace,
    and removes empty sections.
    """
    lines = text.split('\n')
    lines = remove_unwanted_sections(lines)

    # Group lines into sections. The first "section" is the intro.
    sections = []
    current_lines = []
    for line in lines:
        if re.match(r'^==+.*==+$', line.strip()):
            if current_lines:
                sections.append(current_lines)
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        sections.append(current_lines)

    # Process and filter sections
    output_parts = []
    for section_lines in sections:
        # Check for content. A section is empty if it has no text lines with content.
        first_line_is_header = re.match(r'^==+.*==+$', section_lines[0].strip())
        content_lines = section_lines[1:] if first_line_is_header else section_lines
        
        if not any(line.strip() for line in content_lines):
            continue # Skip empty sections

        # If not empty, process the section
        # Strip trailing whitespace from all lines
        processed_section_lines = [l.rstrip() for l in section_lines]

        if first_line_is_header:
            header_line = processed_section_lines.pop(0)
            m = re.match(r'^(==+)\s*(.*?)\s*\1$', header_line)
            if m:
                # This is a well-formed header
                title = m.group(2)
                level = len(m.group(1))
                # Format header and join with its content
                output_parts.append(f"{'#' * level} {title}\n" + '\n'.join(processed_section_lines))
            else:
                # This is a malformed header, treat it as plain text to avoid crashing
                output_parts.append(header_line + '\n' + '\n'.join(processed_section_lines))
        else:
            # This is the intro content
            output_parts.append('\n'.join(processed_section_lines))

    # Join everything with proper spacing
    full_text = '\n\n'.join(part.strip() for part in output_parts if part.strip())
    return full_text

# ======================================================================
# Helper Functions
# ======================================================================

def remove_unwanted_sections(lines):
    """
    Removes sections that are not useful, like 'References' and 'See also'.
    """
    unwanted_headers = [
        "references", "see also", "sources", "citations", 
        "external links", "further reading", "bibliography",
        "notes", "footnotes", "other websites"
    ]
    
    result_lines = []
    skip_section = False
    
    for line in lines:
        header_match = re.match(r'^(==+)\s*(.*?)\s*\1$', line)
        
        if header_match:
            header_text = header_match.group(2).strip().lower()
            skip_section = any(unwanted in header_text for unwanted in unwanted_headers)
        
        if not skip_section:
            result_lines.append(line)
    
    return result_lines

def drop_nested(text, open_delim, close_delim):
    """
    Removes all occurrences of nested delimited text blocks.
    e.g., drop_nested("a {{b {{c}} d}} e", r'{{', r'}}') -> "a  e"
    """
    open_re = re.compile(open_delim)
    close_re = re.compile(close_delim)
    
    events = sorted(
        [(m.start(), 1) for m in open_re.finditer(text)] +
        [(m.start(), -1) for m in close_re.finditer(text)]
    )
    
    level = 0
    start = -1
    spans_to_drop = []

    for pos, type in events:
        if level == 0 and type == 1:
            start = pos
        level += type
        if level == 0 and start != -1:
            spans_to_drop.append((start, pos + len(close_delim)))
            start = -1
            
    for s, e in reversed(spans_to_drop):
        text = text[:s] + text[e:]
            
    return text

def find_balanced(text, open_delim_list, close_delim_list):
    """
    An iterator which identifies balanced opening and closing delimiters.
    """
    open_pat = '|'.join([re.escape(x) for x in open_delim_list])
    after_pat = {o: re.compile(open_pat + '|' + c, re.DOTALL) for o, c in zip(open_delim_list, close_delim_list)}
    
    stack = []
    start = 0
    cur = 0
    start_set = False
    start_pat = re.compile(open_pat)
    next_pat = start_pat
    
    while True:
        next_match = next_pat.search(text, cur)
        if not next_match:
            return
            
        if not start_set:
            start = next_match.start()
            start_set = True
            
        delim = next_match.group(0)
        
        if delim in open_delim_list:
            stack.append(delim)
            next_pat = after_pat[delim]
        else:
            if not stack:
                cur = next_match.end()
                continue

            stack.pop()
            
            if not stack:
                yield start, next_match.end()
                next_pat = start_pat
                start_set = False
        
        cur = next_match.end()
