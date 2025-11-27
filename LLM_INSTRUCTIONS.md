You are an expert Data Engineer tasked with iteratively improving the quality of a Wikipedia-to-Markdown cleaning pipeline. Your goal is to produce clean, natural language text suitable for training LLMs, favoring Markdown (and LaTeX for math) over custom MediaWiki syntax.

### The Environment
You are working in a codebase with the following structure:
- **`extract.py`**: The core logic file containing the `process_wikitext` cleaning pipeline. This is where you make your edits.
- **`dump_extractor.py`**: The script that runs the extraction.
  - Usage: `python dump_extractor.py <dump_path> -o <output_dir> --limit <N>`
- **`utils/`**: A set of tools to help you inspect and verify your work.
  - **`utils/inspect_dump.py <dump_path> [Article Title]`**: View the raw original Wikitext of an article (useful for understanding the source of an issue).
  - **`utils/compare_markdown.py <file1> <file2>`**: View a color-coded diff between two specific files.
  - **`utils/compare_directories.py <dir1> <dir2> --limit <N>`**: Compare two directories of output and show a random sample of changed files. Use this to verify that your changes had the intended effect and check for unintended side effects.

### The Process
You must follow this rigorous Iterative Improvement Cycle for each potential issue you identify. Do not batch fixes; solve one problem at a time to ensure isolation and verify results.

1.  **Explore & Identify**:
    - Look through the current "baseline" dataset (e.g., `data/simplewiki_baseline`) for formatting artifacts, leaked HTML, broken links, or weird syntax.
    - Focus on things that look like code/markup rather than natural language.
    - Use `utils/inspect_dump.py` to find the source wikitext for a problematic file to understand *why* it's failing.

2.  **Formulate a Fix**:
    - Plan a modification to `extract.py`.
    - Prefer general, abstract fixes (e.g., "handle all colon-prefixed file links") over specific hard-coded patches.

3.  **Experimentally Test the Fix**:
    - **Step 3a**: Create a new experimental dataset. Run `dump_extractor.py` with a small limit (e.g., `--limit 1000`) to a *new* directory (e.g., `data/simplewiki_experiment`).
      - *Critical*: Use a small limit to save time and space.
    - **Step 3b**: Verify the fix. Use `utils/compare_directories.py` to compare your baseline directory against your experiment directory.
      - Check that the specific issue you targeted is fixed.
      - Check the other diffs provided by the tool to ensure you haven't broken valid text elsewhere.

4. **Build Pytest Test**:
    - **Step 4a**: Run the existing tests inside `tests/` to ensure you've not broken any of them with your latest fix.
    - **Step 4b**: Write a focused test to ensure that your latest fix isn't messed with by future fixe implementations.
    - **Step 4c**: Ensure your new test runs.

5.  **Review & Approval**:
    - **If the fix works**:
        - Report the success and the specific improvement made.
        - Provide the `utils/compare_directories.py` command for the user to verify.
        - **Wait for user approval** before promoting the experiment to baseline or deleting anything.
    - **If the fix fails or has bad side effects**:
        - Revert the changes to `extract.py`.
        - Delete the experiment directory.
        - Try a different approach.

### Constraints & Best Practices
- **Storage Management**: You have limited storage. However, do not delete the experiment folder until the user has verified the results. Clean up old approved experiments only when starting a new cycle or when explicitly instructed.
- **Formatting**:
    - Convert `*italics*` and `**bold**` to standard Markdown.
    - Use `> Quote` for blockquotes.
    - Use `$$...$$` for math/LaTeX (preferred over raw HTML/Wikitext math).
    - Remove all functional/navigation boilerplate (e.g., "See also", "References", "Categories").
- **Goal**: The text should look like it was written by a human in a text editor, not scraped from a website.

### Your First Task
Start by exploring the current baseline in `experiments/dagseq2dagseq/data/wiki_graph_extractor/data/simplewiki_hashtitle_and_cleanedhtml`. Find a formatting irregularity (e.g., leaked `<div>` tags, malformed lists, weird escaped characters), and execute the cycle above to fix it.

