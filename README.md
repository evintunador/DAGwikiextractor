# DAGWikiExtractor

A streamlined Python tool for processing Wikipedia Cirrus dumps into a clean, link-preserving dataset for training LLMs. This script converts Wikipedia articles from their raw `source_text` in a Cirrus dump into individual Markdown files, making sure that all internal wiki links are converted to standard Markdown links.

This project was originally adapted from the much more complex [attardi/wikiextractor](https://github.com/attardi/wikiextractor) but has been heavily refactored to rely on pre-expanded Cirrus dumps, which dramatically simplifies the extraction and cleaning process.

## Features

-   **Processes Cirrus Dumps**: Directly reads the gzipped, line-delimited JSON format of Wikipedia Cirrus dumps.
-   **Link Preservation**: Converts `[[wiki links]]` and `[[wiki links|with custom text]]` into standard `[Markdown links](wiki_links)`.
-   **Comprehensive Cleaning**: Removes a wide variety of wikitext noise, including:
    -   Template calls (`{{...}}`)
    -   Wikitables (`{|...|}`)
    -   External links (`[http...]`)
    -   Reference tags (`<ref>...`)
    -   Unwanted sections (e.g., "References", "See also", "External links").
-   **Simple & Fast**: With no need for a complex template expansion engine, the script is fast and has no external dependencies.
-   **One File Per Article**: Each Wikipedia article is saved as a cleanly formatted `.md` file.

## Usage

### 1. Download a Wikipedia Dump

This tool is designed to work with Cirrus dumps, which contain the pre-expanded `source_text` we need.

1.  Go to the [Wikimedia Cirrus Dumps page](https://dumps.wikimedia.org/other/cirrussearch/).
2.  Select a recent date (e.g., `20251101/`).
3.  Download a `...-cirrussearch-content.json.gz` file for your language of choice (e.g., `enwiki-20251101-cirrussearch-content.json.gz` for English).

### 2. Run the Extractor

Place the downloaded dump file in your project directory (or a subdirectory like `data/`) and run the script from your terminal:

```bash
python main.py <path_to_dump_file>
```

**Example:**

```bash
# Process the entire dump and save files to the default 'output/' directory
python main.py data/simplewiki-20251027-cirrussearch-content.json.gz

# Process only the first 100 articles for a quick test
python main.py data/simplewiki-20251027-cirrussearch-content.json.gz --limit 100

# Specify a different output directory
python main.py data/simplewiki-20251027-cirrussearch-content.json.gz -o processed_articles/
```

### Command-Line Options

-   `input`: (Required) The path to the input Wikipedia Cirrus dump file (`.json.gz`).
-   `-o, --output`: The directory where extracted Markdown files will be saved. Defaults to `output`.
-   `--limit`: An optional integer to limit the number of articles to process. Very useful for testing.
-   `-q, --quiet`: Suppress progress reporting during extraction.