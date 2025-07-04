#!/usr/bin/env python3

import os
import argparse
from pathlib import Path
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

# File extensions to be treated as binary and skipped if not explicitly handled by gitignore
BINARY_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.zip', '.tar', '.gz', '.rar', '.7z',
    '.woff', '.woff2', '.ttf', '.otf', '.eot',
    '.mp3', '.wav', '.ogg',
    '.mp4', '.mov', '.avi',
}

def is_binary_file(filepath):
    """
    Checks if a file is binary by checking its extension.
    """
    return os.path.splitext(filepath)[1].lower() in BINARY_EXTENSIONS

def load_gitignore_spec(repo_root):
    """
    Loads .gitignore patterns from the repository root.
    """
    gitignore_path = Path(repo_root) / '.gitignore'
    if gitignore_path.exists():
        with gitignore_path.open('r') as f:
            return PathSpec.from_lines(GitWildMatchPattern, f)
    return PathSpec([]) # Return an empty spec if no .gitignore

def generate_export_content(paths_to_scan, gitignore_spec, verbose=False):
    """
    Walks through the specified paths and generates the concatenated file content,
    respecting .gitignore rules.
    """
    output_content = []
    exported_file_count = 0
    # Determine repo_root based on the script's location
    script_dir = Path(__file__).parent.resolve()
    repo_root = script_dir # Assuming script is in edi-lens/

    for start_path_str in paths_to_scan:
        # Make start_path absolute relative to repo_root
        abs_start_path = repo_root / start_path_str
        if not abs_start_path.exists():
            print(f"Warning: Path '{start_path_str}' does not exist. Skipping.")
            continue

        for root_str, dirs, files in os.walk(abs_start_path, topdown=True):
            root = Path(root_str)
            
            # Filter out directories based on .gitignore before recursing
            # Create a copy of dirs to modify in place
            dirs_to_prune = []
            for d in dirs:
                dir_path = root / d
                relative_dir_path = dir_path.relative_to(repo_root)
                if gitignore_spec.match_file(str(relative_dir_path) + '/'): # Add / to match directories
                    if verbose:
                        print(f"Skipping ignored directory: {relative_dir_path}")
                    dirs_to_prune.append(d)
            
            for d in dirs_to_prune:
                dirs.remove(d)

            for file in sorted(files):
                file_path = root / file
                relative_file_path = file_path.relative_to(repo_root)

                # Check .gitignore for file exclusion
                if gitignore_spec.match_file(str(relative_file_path)):
                    if verbose:
                        print(f"Skipping ignored file: {relative_file_path}")
                    continue

                # Check if the file is binary (not already ignored by .gitignore)
                if is_binary_file(file_path):
                    if verbose:
                        print(f"Skipping binary file: {relative_file_path}")
                    continue

                if verbose:
                    print(f"Exporting: {relative_file_path}")
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    output_content.append(f"-- START OF FILE {relative_file_path} --")
                    output_content.append(content)
                    output_content.append(f"-- END OF FILE {relative_file_path} --\n")
                    exported_file_count += 1
                except Exception as e:
                    print(f"Could not read file {file_path}: {e}")
    
    return "\n".join(output_content), exported_file_count

def main():
    """
    Main function to parse arguments and run the export process.
    """
    parser = argparse.ArgumentParser(
        description="A utility to export project files into a single text file for LLM context, respecting .gitignore.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        '--frontend', 
        action='store_true', 
        help='Only export the frontend directory (frontend/src and relevant top-level frontend config).'
    )
    parser.add_argument(
        '--backend', 
        action='store_true', 
        help='Only export the backend directory (backend/src and relevant top-level backend config).'
    )
    parser.add_argument(
        '-o', '--output', 
        default='llm_export.txt', 
        help='Name of the output file. (Default: llm_export.txt)'
    )
    parser.add_argument(
        '-v', '--verbose', 
        action='store_true', 
        help='Print the name of each file as it is being exported.'
    )

    args = parser.parse_args()

    # Determine repo_root based on the script's location
    script_dir = Path(__file__).parent.resolve()
    repo_root = script_dir # Assuming script is in edi-lens/
    gitignore_spec = load_gitignore_spec(repo_root)

    # Determine which paths to scan
    paths_to_scan = []
    if args.frontend and not args.backend:
        paths_to_scan.append('frontend/src')
        # Add specific frontend config files
        paths_to_scan.extend([
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
        ])
    elif args.backend and not args.frontend:
        paths_to_scan.append('backend/src')
        paths_to_scan.append('backend/tests')
        # Add specific backend config files
        paths_to_scan.extend([
            'backend/pyproject.toml',
            'backend/poetry.lock',
            'backend/alembic.ini',
            'backend/pytest.ini',
            'backend/Dockerfile',
            'backend/entrypoint.sh',
        ])
    else:
        # Default to both if no flags are specified or if both are specified
        paths_to_scan.extend(['frontend/src', 'backend/src'])
        # Add top-level config files
        paths_to_scan.extend([
            'docker-compose.yml',
            'export_for_llm.py', # Include itself for context
            'run_app.sh',
            'backend/README.md',
            'frontend/README.md',
            '.github/workflows/fly-deploy.yml',
        ])
        # Add test and migration directories
        paths_to_scan.extend([
            'backend/tests',
            'frontend/e2e',
            'backend/alembic/versions',
        ])
        # Add common config files from frontend and backend
        paths_to_scan.extend([
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
            'backend/pyproject.toml',
            'backend/poetry.lock',
            'backend/alembic.ini',
            'backend/pytest.ini',
            'backend/Dockerfile',
            'backend/entrypoint.sh',
        ])


    print(f"Starting export...")
    print(f"Scanning paths: {', '.join(paths_to_scan)}")
    print(f"Outputting to: {args.output}")

    # Generate the content
    content, count = generate_export_content(paths_to_scan, gitignore_spec, args.verbose)

    # Write the content to the output file
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\nSuccess! Exported {count} files to '{args.output}'.")
    except Exception as e:
        print(f"\nError writing to output file: {e}")


if __name__ == "__main__":
    main()