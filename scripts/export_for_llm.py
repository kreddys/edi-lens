#!/usr/bin/env python3

import os
import re
import argparse
from pathlib import Path
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

# --- ANSI Color Codes ---
class Colors:
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    CYAN = '\033[96m'

# --- File Type and Path Configuration ---
BINARY_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.zip', '.tar', '.gz', '.rar', '.7z',
    '.woff', '.woff2', '.ttf', '.otf', '.eot',
    '.mp3', '.wav', '.ogg',
    '.mp4', '.mov', '.avi',
}

# Directories to always ignore.
IGNORE_PATHS = [
    'backend/migrations',
    'admin-ui/tmp',
]

# Filenames to always ignore by default.
IGNORE_FILENAMES = {
    '.env.dev',
    'poetry.lock',
    'package-lock.json',
}

# --- Configuration for Optimizations ---
TRUNCATE_THRESHOLD_BYTES = 100 * 1024  # 100 KB
TRUNCATE_LINES = 100

def is_binary_file(filepath):
    return os.path.splitext(filepath)[1].lower() in BINARY_EXTENSIONS

def load_gitignore_spec(repo_root):
    gitignore_path = Path(repo_root) / '.gitignore'
    if gitignore_path.exists():
        with gitignore_path.open('r') as f:
            return PathSpec.from_lines(GitWildMatchPattern, f)
    return PathSpec([])

def format_file_size(bytes_size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} PB"


def get_files_to_process(paths_to_scan, gitignore_spec, args):
    repo_root = Path().resolve()
    processed_files = set()
    
    ignore_path_set = set(Path(p).as_posix().rstrip('/') for p in IGNORE_PATHS)
    if args.no_docs:
        ignore_path_set.add('docs')
    if args.no_tests:
        ignore_path_set.add('backend/tests')

    ignore_filename_set = IGNORE_FILENAMES.copy()
    if args.include_lockfiles:
        ignore_filename_set.discard('poetry.lock')
        ignore_filename_set.discard('package-lock.json')

    def is_ignored(file_path: Path) -> bool:
        rel_path_str = file_path.relative_to(repo_root).as_posix()
        if gitignore_spec.match_file(rel_path_str):
            return True
        if any(rel_path_str.startswith(p) for p in ignore_path_set):
            return True
        if file_path.name in ignore_filename_set:
            return True
        return False

    for path_str in paths_to_scan:
        path = repo_root / path_str
        if not path.exists():
            print(f"{Colors.YELLOW}Warning: Path '{path_str}' does not exist. Skipping.{Colors.RESET}")
            continue

        if path.is_file():
            if not is_ignored(path):
                processed_files.add(path)
        elif path.is_dir():
            for file in sorted(path.rglob('*')):
                if file.is_file() and not is_ignored(file):
                    processed_files.add(file)
    
    return sorted(list(processed_files))

def main():
    parser = argparse.ArgumentParser(
        description="Export project files into a single text file for LLM context, respecting .gitignore.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--backend', action='store_true', help='Export only the backend service and related configs.')
    parser.add_argument('--admin', action='store_true', help='Export only the admin-ui service and related configs.')
    parser.add_argument('-o', '--output', default='llm_export.txt', help='Output file name. (Default: llm_export.txt)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Print each file and its size as it is exported.')
    parser.add_argument('--include-lockfiles', action='store_true', help='Include poetry.lock and package-lock.json files (excluded by default).')
    parser.add_argument('--no-docs', action='store_true', help='Exclude the /docs directory.')
    parser.add_argument('--no-tests', action='store_true', help='Exclude the backend/tests directory.')
    args = parser.parse_args()

    repo_root = Path().resolve()
    gitignore_spec = load_gitignore_spec(repo_root)

    scan_all = not args.backend and not args.admin
    paths_to_scan = []

    if args.backend or scan_all:
        paths_to_scan.extend([
            'backend/src', 'backend/alembic', 'backend/scripts', 'backend/data/seed', 'backend/tests',
            'backend/pyproject.toml', 'backend/alembic.ini', 'backend/pytest.ini', 'backend/.dockerignore',
            'backend/.dockerignore', 'backend/README.md',
        ])

    if args.admin or scan_all:
        paths_to_scan.extend([
            'admin-ui/src', 'admin-ui/package.json', 'admin-ui/tsconfig.json', 'admin-ui/vite.config.ts',
            'admin-ui/tsconfig.node.json', 'admin-ui/index.html',
            'admin-ui/README.md',
        ])

    if args.backend or args.admin or scan_all:
        paths_to_scan.extend([
            '.gitignore', 'README.md',
            '.env.dev.example', '.env.test.example', '.env.prod.example',
            'docker',
            'run.sh', 'scripts/queries.sql', 'docs', 'backend/data/knowledge', 'backend/data/edi_schemas/837.5010.X222.A1.json'
        ])
    
    unique_paths = list(dict.fromkeys(paths_to_scan))
    
    print("🔍 Starting export...")
    if args.verbose: print(f"📂 Scanning paths:\n  - " + "\n  - ".join(unique_paths))
    print(f"📄 Output file: {args.output}\n")
    
    files_to_process = get_files_to_process(unique_paths, gitignore_spec, args)
    
    output_chunks = []
    total_exported_bytes = 0

    for file_path in files_to_process:
        try:
            relative_file_path = file_path.relative_to(repo_root).as_posix()
            if is_binary_file(file_path):
                continue

            content_bytes = file_path.read_bytes()
            original_file_size = len(content_bytes)
            
            content = content_bytes.decode('utf-8', errors='ignore').strip()
            content = re.sub(r'\n{3,}', '\n\n', content)

            was_truncated = False
            if original_file_size > TRUNCATE_THRESHOLD_BYTES:
                was_truncated = True
                lines = content.splitlines()
                content = "\n".join(lines[:TRUNCATE_LINES])
                content += f"\n\n... [File truncated at {TRUNCATE_LINES} lines] ..."

            if args.verbose:
                size_str = format_file_size(original_file_size)
                if was_truncated:
                    print(f"{Colors.RED}Exporting (TRUNCATED): {relative_file_path} ({size_str}){Colors.RESET}")
                elif original_file_size > 10 * 1024:
                    print(f"{Colors.YELLOW}Exporting: {relative_file_path} ({size_str}){Colors.RESET}")
                else:
                    print(f"Exporting: {relative_file_path} ({size_str})")

            final_content_bytes = content.encode('utf-8')
            output_chunks.append(f"--- START OF FILE {relative_file_path} ---")
            output_chunks.append(final_content_bytes.decode('utf-8'))
            output_chunks.append(f"-- END OF FILE {relative_file_path} --\n")
            
            total_exported_bytes += len(final_content_bytes)

        except Exception as e:
            print(f"Could not read file {file_path}: {e}")

    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(f"--- START OF FILE {args.output} ---\n\n")
            f.write("\n".join(output_chunks))

        print(f"\n✅ Success! Exported {len(files_to_process)} files.")
        print(f"📦 Total export size: {Colors.CYAN}{format_file_size(total_exported_bytes)}{Colors.RESET}")
        print(f"📝 Output written to: {args.output}")
    except Exception as e:
        print(f"\n{Colors.RED}❌ Error writing to output file: {e}{Colors.RESET}")


if __name__ == "__main__":
    main()