import gzip
import json
import os

def inspect_cirrus_dump(file_path, num_articles=1):
    """
    Reads and prints the full data structure of the first article 
    from a gzipped Cirrus search dump file to inspect for link data.
    """
    print(f"Inspecting file: {file_path}\n")
    
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    articles_inspected = 0
    with gzip.open(file_path, 'rt', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                # We are looking for an article object, which should have a title and text.
                if 'title' in data and 'text' in data:
                    print("-" * 80)
                    print(f"Found an article: '{data.get('title')}'")
                    print("Inspecting its JSON structure...")
                    print("-" * 80)
                    
                    # Print all keys in the JSON object
                    print("Available keys in this article object:")
                    for key in data.keys():
                        print(f"- {key}")
                    print("-" * 80)

                    # Print some of the values to see their content
                    print("Value snippets for some interesting keys:")
                    for key, value in data.items():
                        if isinstance(value, str):
                            print(f"'{key}': '{value[:200]}...'")
                        elif isinstance(value, list):
                             print(f"'{key}': {value[:5]}...")
                        else:
                            print(f"'{key}': {value}")

                    print("-" * 80)
                    print("Full text snippet (first 1000 characters):")
                    print(data.get('text', '')[:1000])
                    print("-" * 80)
                    
                    articles_inspected += 1
                    if articles_inspected >= num_articles:
                        break
            except json.JSONDecodeError:
                continue

if __name__ == '__main__':
    script_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(script_dir, '..'))
    file_to_inspect = os.path.join(project_root, 'data', 'simplewiki-20251027-cirrussearch-content.json.gz')
    
    inspect_cirrus_dump(file_to_inspect)
