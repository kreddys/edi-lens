#!/usr/bin/env python3

import os
import re
import argparse
from pathlib import Path
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

BINARY_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.zip', '.tar', '.gz', '.rar', '.7z',
    '.woff', '.woff2', '.ttf', '.otf', '.eot',
    '.mp3', '.wav', '.ogg',
    '.mp4', '.mov', '.avi',
}

IGNORE_PATHS = [
    'backend/migrations',         # Specific directory
    'admin-ui/tmp',               # Another directory
]

IGNORE_FILENAMES = [
    '.env.local',
    '837.5010.X222.A1.json',               # Ignore this file name anywhere
]

# --- Configuration for Optimizations ---
TRUNCATE_THRESHOLD_KB = 50
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
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"

def generate_export_content(paths_to_scan, gitignore_spec, verbose=False):
    output_chunks = []
    exported_file_count = 0
    total_export_size = 0
    repo_root = Path().resolve()

    ignore_path_set = set(Path(p).as_posix().rstrip('/') for p in IGNORE_PATHS)
    ignore_filename_set = set(IGNORE_FILENAMES)

    def is_ignored(file_path: Path) -> bool:
        rel_path = file_path.relative_to(repo_root).as_posix()

        # Match directory or full path
        if any(rel_path == ignore_dir or rel_path.startswith(ignore_dir + '/') for ignore_dir in ignore_path_set):
            if verbose:
                print(f"Ignoring by path: {rel_path}")
            return True

        # Match filename (anywhere)
        if file_path.name in ignore_filename_set:
            if verbose:
                print(f"Ignoring by filename: {file_path.name}")
            return True

        return False

    def process_file(file_path):
        nonlocal exported_file_count, total_export_size
        try:
            relative_file_path = file_path.relative_to(repo_root).as_posix()

            if gitignore_spec.match_file(relative_file_path) or is_binary_file(file_path) or is_ignored(file_path):
                if verbose:
                    print(f"Skipping ignored/binary file: {relative_file_path}")
                return

            content_bytes = file_path.read_bytes()
            content = content_bytes.decode('utf-8', errors='ignore')

            if verbose:
                print(f"Exporting: {relative_file_path} ({format_file_size(len(content_bytes))})")

            content = re.sub(r'\n{3,}', '\n\n', content.strip())

            output_chunks.append(f"--- START OF FILE {relative_file_path} ---")
            output_chunks.append(content)
            output_chunks.append(f"-- END OF FILE {relative_file_path} --\n")

            exported_file_count += 1
            total_export_size += len(content_bytes)

        except Exception as e:
            print(f"Could not read file {file_path}: {e}")

    for path_str in paths_to_scan:
        path = repo_root / path_str
        if not path.exists():
            print(f"Warning: Path '{path_str}' does not exist. Skipping.")
            continue

        if path.is_file():
            process_file(path)
        elif path.is_dir():
            for file in sorted(path.rglob('*')):
                if file.is_file():
                    process_file(file)

    return "\n".join(output_chunks), exported_file_count, total_export_size



def main():
    parser = argparse.ArgumentParser(
        description="Export project files into a single text file for LLM context, respecting .gitignore.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument('--frontend', action='store_true', help='Export frontend directory and config.')
    parser.add_argument('--backend', action='store_true', help='Export backend directory and config.')
    parser.add_argument('--admin', action='store_true', help='Export admin-ui directory (refine.dev app).')
    parser.add_argument('-o', '--output', default='llm_export.txt', help='Output file name. (Default: llm_export.txt)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Print each file as it is being exported.')

    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    gitignore_spec = load_gitignore_spec(repo_root)

    scan_all = not args.frontend and not args.backend and not args.admin
    paths_to_scan = []

    if args.frontend or scan_all:
        paths_to_scan.extend([
            'frontend/src',
            'frontend/e2e',
            'frontend/package.json',
            'frontend/package-lock.json',
            'frontend/tsconfig.json',
            'frontend/tsconfig.app.json',
            'frontend/tsconfig.node.json',
            'frontend/vite.config.ts',
            'frontend/tailwind.config.js',
            'frontend/postcss.config.cjs',
            'frontend/eslint.config.js',
            'frontend/nginx.conf',
            'frontend/Dockerfile',
            'frontend/README.md',
        ])

    if args.backend or scan_all:
        paths_to_scan.extend([
            'backend/src',
            'backend/tests',
            'backend/alembic',
            'backend/scripts',
            'backend/seed_data',
            'backend/pyproject.toml',
            'backend/poetry.lock',
            'backend/alembic.ini',
            'backend/pytest.ini',
            'backend/Dockerfile',
            'backend/.dockerignore',
            'backend/entrypoint.sh',
            'backend/README.md',
        ])

    if args.admin or scan_all:
        paths_to_scan.extend([
            'admin-ui/src',
            'admin-ui/package.json',
            'admin-ui/tsconfig.json',
            'admin-ui/vite.config.ts',
            'admin-ui/tsconfig.node.json',
            'admin-ui/nginx.conf',
            'admin-ui/index.html',
            'admin-ui/Dockerfile',
            'admin-ui/Dockerfile.dev',
            'admin-ui/README.md',
        ])

    # Shared project-level files
    paths_to_scan.extend([
        '.gitignore',
        'README.md',
        'Caddyfile',
        '.env.example',
        '.env.local.example',
        '.env.prod.example',
        'docker-compose.yml',
        'docker-compose.dev.yml',
        'docker-compose.prod.yml',
        'docker-compose.run.yml',
        'scripts/run_app.sh',
        'scripts/queries.sql',
        'scripts/export_for_llm.py',
        '.github/workflows',
        'docs'
    ])

    unique_paths = list(dict.fromkeys(paths_to_scan))  # Preserve order, remove duplicates

    print("🔍 Starting export...")
    print(f"📂 Scanning paths:\n  - " + "\n  - ".join(unique_paths))
    print(f"📄 Output file: {args.output}\n")

    content, count, total_size = generate_export_content(unique_paths, gitignore_spec, args.verbose)

    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(f"--- START OF FILE {args.output} ---\n")
            f.write(content)

        print(f"\n✅ Success! Exported {count} files.")
        print(f"📦 Total export size: {format_file_size(total_size)}")
        print(f"📝 Output written to: {args.output}")
    except Exception as e:
        print(f"\n❌ Error writing to output file: {e}")

if __name__ == "__main__":
    main()
