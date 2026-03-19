import os
import re

def replace_in_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return

    orig_content = content
    # Replace exact matches
    content = re.sub(r'\bDebounce\b', 'Ironpass', content)
    content = re.sub(r'\bdebounce\b', 'ironpass', content)
    content = re.sub(r'\bDEBOUNCE\b', 'IRONPASS', content)
    
    # Also without word boundaries, just in case
    content = content.replace('Debounce', 'Ironpass')
    content = content.replace('debounce', 'ironpass')
    content = content.replace('DEBOUNCE', 'IRONPASS')

    if content != orig_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath}")

def main():
    exclude_dirs = {'.git', '.gemini', '__pycache__', 'node_modules', 'venv', 'env', '.env', '.pytest_cache'}
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file == 'rename_script.py':
                continue
            filepath = os.path.join(root, file)
            replace_in_file(filepath)

if __name__ == '__main__':
    main()
