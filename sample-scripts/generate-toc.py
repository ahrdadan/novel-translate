"""
Generate Table of Contents (toc.json) from HTML Files.

Usage Examples:
1. Run with default settings (targets 'novel-html' folder in the same directory, starts chapter at 1):
   python generate-toc.py

2. Specify a custom directory containing the HTML files:
   python generate-toc.py -d path/to/your/html_folder
   # Or using long argument
   python generate-toc.py --dir path/to/your/html_folder

3. Specify a custom starting chapter number (e.g., start at chapter 15):
   python generate-toc.py -s 15
   # Or using long argument
   python generate-toc.py --start 15

4. Combine both custom directory and custom starting chapter:
   python generate-toc.py -d my-novel-folder -s 21

The script will read all HTML files in the target folder alphabetically, 
extract the text inside the first <h1> tag for the title, and generate 
a 'toc.json' file inside that target directory.
"""
import os
import json
import argparse
import re
import html
from pathlib import Path

def extract_title(file_path):
    """
    Extracts text from the first <h1> tag in an HTML file.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Find the first <h1> tag
            match = re.search(r'<h1[^>]*>(.*?)</h1>', content, re.IGNORECASE | re.DOTALL)
            if match:
                inner_html = match.group(1)
                # Remove any nested HTML tags within <h1>
                text = re.sub(r'<[^>]+>', '', inner_html)
                # Unescape HTML entities (e.g. &amp; -> &)
                return html.unescape(text).strip()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return "Unknown Title"

def generate_toc(target_dir, start_chapter):
    """
    Scans a directory for HTML files, extracts their titles, 
    and generates a toc.json file in the same directory.
    """
    target_path = Path(target_dir).resolve()
    if not target_path.exists() or not target_path.is_dir():
        print(f"Error: Directory '{target_dir}' does not exist.")
        return

    # Find all html files and sort them alphabetically
    html_files = sorted([
        f for f in target_path.iterdir() 
        if f.suffix.lower() in ['.html', '.htm'] and f.is_file()
    ])
    
    if not html_files:
        print(f"No HTML files found in '{target_path}'.")
        return

    toc = []
    chapter_num = start_chapter

    for file_path in html_files:
        title = extract_title(file_path)
        toc.append({
            "chapterNumber": chapter_num,
            "title": title,
            "file": file_path.name
        })
        chapter_num += 1

    # Save to toc.json in the same folder as the HTML files
    toc_file = target_path / 'toc.json'
    with open(toc_file, 'w', encoding='utf-8') as f:
        json.dump(toc, f, indent=2, ensure_ascii=False)

    print(f"Successfully generated toc.json at {toc_file}")
    print(f"Total entries: {len(toc)}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate toc.json from HTML files based on their <h1> tags.')
    parser.add_argument('-d', '--dir', default='novel-html', 
                        help='Path to the directory containing HTML files. (default: novel-html)')
    parser.add_argument('-s', '--start', type=int, default=1, 
                        help='Starting chapter number. (default: 1)')
    
    args = parser.parse_args()
    
    # Resolve relative to where the script is located
    script_dir = Path(__file__).parent
    
    target_directory = args.dir
    # If the provided path is not absolute, treat it as relative to this script
    if not Path(target_directory).is_absolute():
        target_directory = script_dir / target_directory
        
    generate_toc(target_directory, args.start)
