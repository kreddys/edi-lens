#!/usr/bin/env python3

import os
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

def is_binary_file(filepath):
    return os.path.splitext(filepath)[1].lower() in BINARY_EXTENSIONS

def load_gitignore_spec(repo_root):
    gitignore_path = Path(repo_root) / '.gitignore'
    if gitignore_path.exists():
        with gitignore_path.open('r') as f:
            return PathSpec.from_lines(GitWildMatchPattern, f)
    return PathSpec([])

def generate_export_content(paths_to_scan, gitignore_spec, verbose=False):
    output_chunks = []
    exported_file_count = 0
    repo_root = Path(__file__).resolve().parent.parent

    def process_file(file_path):
        nonlocal exported_file_count
        relative_file_path = file_path.relative_to(repo_root)

        if gitignore_spec.match_file(str(relative_file_path)):
            if verbose:
                print(f"Skipping ignored file: {relative_file_path}")
            return

        if is_binary_file(file_path):
            if verbose:
                print(f"Skipping binary file: {relative_file_path}")
            return

        if verbose:
            print(f"Exporting: {relative_file_path}")

        try:
            with file_path.open('r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            output_chunks.append(f"-- START OF FILE {relative_file_path} --")
            output_chunks.append(content)
            output_chunks.append(f"-- END OF FILE {relative_file_path} --\n")
            exported_file_count += 1
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
            for root_str, dirs, files in os.walk(path, topdown=True):
                root = Path(root_str)
                dirs_to_prune = [d for d in dirs if gitignore_spec.match_file(str((root / d).relative_to(repo_root)) + '/')]
                for d in dirs_to_prune:
                    if verbose:
                        print(f"Skipping ignored directory: {(root / d).relative_to(repo_root)}/")
                    dirs.remove(d)

                for file in sorted(files):
                    process_file(root / file)

    return "\n".join(output_chunks), exported_file_count

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

    # Always include these shared project-level files
    paths_to_scan.extend([
        '.gitignore',
        'README.md',
        '.env.example',
        'docker-compose.yml',
        'docker-compose.dev.yml',
        'scripts/run_app.sh',
        'scripts/queries.sql',
        'docs'
    ])

    unique_paths = list(dict.fromkeys(paths_to_scan))

    print(f"Starting export...")
    print(f"Scanning paths: {', '.join(unique_paths)}")
    print(f"Outputting to: {args.output}")

    content, count = generate_export_content(unique_paths, gitignore_spec, args.verbose)

    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(f"--- START OF FILE {args.output} ---\n")
            f.write(content)
        print(f"\nSuccess! Exported {count} files to '{args.output}'.")
    except Exception as e:
        print(f"\nError writing to output file: {e}")

if __name__ == "__main__":
    main()
