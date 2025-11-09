#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DAGWikiGraphBuilder: A tool to build a link graph from a directory of 
Markdown files produced by DAGWikiExtractor.
"""
import argparse
import glob
import json
import logging
import os
import re
from multiprocessing import Pool, cpu_count
from functools import partial
from itertools import islice
from tqdm import tqdm
from timeit import default_timer

# ===========================================================================
# Worker Process Function
# ===========================================================================

def extract_links_worker(filepath):
    """
    Reads a single markdown file, extracts its title and all outgoing links.
    The title is assumed to be the first line, formatted as '# Title'.
    Links are standard markdown [text](link) format.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # The title is the first line, stripped of '# ' and newline
            title_line = f.readline()
            if not title_line.startswith('# '):
                return None # Skip files that don't have a clear title header
            title = title_line[2:].strip()

            # Read the rest of the file and find all markdown links
            content = f.read()
            char_count = len(title_line) + len(content)
            
            # This regex finds links but avoids image links ![...](...)
            # It captures the link target from [text](target)
            links = re.findall(r'\[[^!\]]*?\]\((.*?)\)', content)
            
            # The link target is the filename without the '.md' extension
            # We also decode any URL-encoded characters
            from urllib.parse import unquote
            outgoing_links = {unquote(link.replace('_', ' ')) for link in links}

            return (title, list(outgoing_links), char_count)
    except Exception as e:
        logging.warning(f"Could not process file {filepath}: {e}")
        return None

# ===========================================================================
# Main Execution
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        prog="DAGWikiGraphBuilder",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "input_dir",
        help="Directory containing the extracted Markdown files."
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output file for the graph (default: 'graph.jsonl' inside the input directory)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of articles to process (for testing)"
    )
    parser.add_argument(
        "-p", "--processes",
        type=int,
        default=cpu_count() - 1,
        help=f"Number of worker processes to use (default: {cpu_count() - 1})"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress progress reporting"
    )
    args = parser.parse_args()

    # If no output file is specified, default to graph.jsonl inside the input dir
    if args.output is None:
        args.output = os.path.join(args.input_dir, 'graph.jsonl')

    # Configure logging
    log_level = logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')

    if not os.path.isdir(args.input_dir):
        logging.error(f"Input directory not found: {args.input_dir}")
        return

    # --- File Discovery ---
    logging.info("Discovering markdown files...")
    # Using an iterator for memory efficiency with large numbers of files
    md_files_iterator = glob.iglob(os.path.join(args.input_dir, '**', '*.md'), recursive=True)
    
    # Apply limit if specified
    if args.limit:
        md_files_iterator = islice(md_files_iterator, args.limit)
    
    # We need a list for the progress bar, so we realize the iterator here
    md_files = list(md_files_iterator)

    if not md_files:
        logging.error("No markdown files found in the input directory.")
        return
        
    logging.info(f"Found {len(md_files)} markdown files to process.")

    # --- Parallel Link Extraction ---
    logging.info(f"Starting link extraction with {args.processes} workers...")
    start_time = default_timer()
    
    with Pool(processes=args.processes) as pool:
        # The main process will read the file and put articles into the pool
        results_iterator = pool.imap_unordered(extract_links_worker, md_files, chunksize=100)
        
        progress_bar = tqdm(
            results_iterator,
            total=len(md_files),
            desc="Extracting links",
            unit=" files",
            disable=args.quiet
        )
        
        # Filter out None results from files that couldn't be processed
        link_data = [result for result in progress_bar if result]

    duration = default_timer() - start_time
    logging.info(f"Link extraction finished in {duration:.2f}s.")

    # --- Graph Aggregation ---
    logging.info("Aggregating link data into a graph...")
    graph = {}

    # First pass: add all nodes and their outgoing links
    for title, outgoing_links, char_count in link_data:
        if title not in graph:
            graph[title] = {'outgoing': [], 'incoming': [], 'char_count': 0}
        # We use a set to avoid duplicate links from the same article
        graph[title]['outgoing'].extend(outgoing_links)
        graph[title]['char_count'] = char_count
    
    # Second pass: build the incoming links
    for source_title, data in graph.items():
        for target_title in data['outgoing']:
            if target_title in graph:
                graph[target_title]['incoming'].append(source_title)
            # Optional: handle dangling links (links to pages not in the dump)
            # else:
            #     logging.debug(f"Dangling link found from '{source_title}' to '{target_title}'")

    # --- Sort and Write Output ---
    logging.info(f"Sorting and writing graph to {args.output}...")
    
    # Sort the graph keys (article titles) alphabetically
    sorted_titles = sorted(graph.keys())
    
    with open(args.output, 'w', encoding='utf-8') as f:
        progress_bar = tqdm(
            sorted_titles,
            desc="Writing JSONL",
            unit=" nodes",
            disable=args.quiet
        )
        for title in progress_bar:
            node_data = {
                'title': title,
                'char_count': graph[title]['char_count'],
                'outgoing': sorted(list(set(graph[title]['outgoing']))),
                'incoming': sorted(list(set(graph[title]['incoming'])))
            }
            f.write(json.dumps(node_data) + '\n')
            
    logging.info("Graph construction complete.")


if __name__ == '__main__':
    main()
