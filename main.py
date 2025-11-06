#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DAGWikiExtractor: A streamlined tool to extract and clean text from 
Wikipedia Cirrus dumps, converting articles into individual Markdown files
with preserved internal links.
"""
import argparse
import gzip
import json
import logging
import os
import re
import sys
from timeit import default_timer

from extract import process_wikitext

# ===========================================================================
# Helper Functions
# ===========================================================================

def get_safe_filename(title):
    """
    Converts an article title into a safe, valid filename.
    """
    # Replace characters that are invalid in filenames with an underscore
    safe_name = re.sub(r'[/\\?%*:|"<>]', '_', title)
    # Trim whitespace from the ends
    safe_name = safe_name.strip()
    # Reduce multiple underscores to a single one
    safe_name = re.sub(r'__+', '_', safe_name)
    # Ensure the filename is not excessively long
    if len(safe_name) > 200:
        safe_name = safe_name[:200]
    return safe_name + '.md'

# ===========================================================================
# Core Processing Logic
# ===========================================================================

def process_dump(input_file, output_dir, limit=None):
    """
    Reads a Wikipedia Cirrus dump, processes each article, and saves it
    as a Markdown file.

    :param input_file: Path to the .json.gz Cirrus dump file.
    :param output_dir: Directory to save the output .md files.
    :param limit: Optional number of articles to process.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    logging.info(f"Starting extraction from '{input_file}'...")
    start_time = default_timer()
    articles_processed = 0

    with gzip.open(input_file, 'rt', encoding='utf-8') as f:
        for line in f:
            try:
                article = json.loads(line)
            except json.JSONDecodeError:
                # Skip metadata lines or malformed JSON
                continue
            
            # We are interested in articles from the main namespace (namespace 0)
            if article.get('namespace') == 0 and 'source_text' in article:
                title = article['title']
                source_text = article['source_text']

                # Process the raw wikitext through our cleaning pipeline
                final_text = process_wikitext(source_text)
                
                # Save to file
                output_filename = get_safe_filename(title)
                output_path = os.path.join(output_dir, output_filename)
                
                with open(output_path, 'w', encoding='utf-8') as out_file:
                    out_file.write(f"# {title}\n\n")
                    out_file.write(final_text)
                
                articles_processed += 1
                
                if articles_processed % 1000 == 0:
                    logging.info(f"Processed {articles_processed} articles...")
                
                if limit and articles_processed >= limit:
                    logging.info(f"Reached article limit of {limit}. Stopping.")
                    break
    
    duration = default_timer() - start_time
    logging.info(
        f"Finished processing {articles_processed} articles in {duration:.2f}s "
        f"({articles_processed / duration:.2f} art/s)"
    )

# ===========================================================================
# Main Execution
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        prog="DAGWikiExtractor",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "input", 
        help="Input Wikipedia Cirrus dump file (.json.gz)"
    )
    parser.add_argument(
        "-o", "--output", 
        default="output",
        help="Directory for extracted Markdown files (default: 'output')"
    )
    parser.add_argument(
        "--limit", 
        type=int, 
        default=None,
        help="Limit the number of articles to process (for testing)"
    )
    parser.add_argument(
        "-q", "--quiet", 
        action="store_true", 
        help="Suppress progress reporting"
    )
    args = parser.parse_args()

    # Configure logging
    log_level = logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')

    process_dump(args.input, args.output, args.limit)

if __name__ == '__main__':
    main()
