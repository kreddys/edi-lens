#!/usr/bin/env python3

import os
import argparse

# --- Configuration for files/directories to exclude ---
# These patterns are checked against directory and file names.
DEFAULT_EXCLUDE_DIRS = {
    "node_modules",
    ".venv",
    "__pycache__",
    ".git",
    ".vscode",
    "dist",
    "build",
    ".pytest_cache",
    "postgres-data",
    "alembic", # Usually not needed for LLM context
}

DEFAULT_EXCLUDE_FILES = {
    ".DS_Store",
    "poetry.lock",
    "package-lock.json",
    ".env",
    "run_app.sh", # Exclude the script itself
    "export_for_llm.py",
}

# File extensions to be treated as binary and skipped
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
    Checks if a file is binary by checking its extension or trying to read it.
    """
    # First, check by extension for common binary types
    if os.path.splitext(filepath)[1].lower() in BINARY_EXTENSIONS:
        return True
    
    # As a fallback, try to read a small chunk of the file
    try:
        with open(filepath, 'tr') as check_file:
            check_file.read(1024)
            return False
    except (UnicodeDecodeError, PermissionError):
        return True
    except Exception:
        # If any other error occurs, assume it's not a text file we want
        return True

def generate_export_content(paths_to_scan, exclude_dirs, exclude_files, verbose=False):
    """
    Walks through the specified paths and generates the concatenated file content.
    """
    output_content = []
    exported_file_count = 0

    for start_path in paths_to_scan:
        if not os.path.exists(start_path):
            print(f"Warning: Path '{start_path}' does not exist. Skipping.")
            continue

        for root, dirs, files in os.walk(start_path, topdown=True):
            # Prune directories from the walk to avoid descending into them
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in sorted(files):
                # Check for file-level exclusions
                if file in exclude_files:
                    continue

                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, start='.')

                # Check if the file is binary
                if is_binary_file(file_path):
                    if verbose:
                        print(f"Skipping binary file: {relative_path}")
                    continue

                if verbose:
                    print(f"Exporting: {relative_path}")
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    output_content.append(f"--- START OF FILE {relative_path} ---")
                    output_content.append(content)
                    output_content.append(f"--- END OF FILE {relative_path} ---\n")
                    exported_file_count += 1
                except Exception as e:
                    print(f"Could not read file {file_path}: {e}")
    
    return "\n".join(output_content), exported_file_count

def main():
    """
    Main function to parse arguments and run the export process.
    """
    parser = argparse.ArgumentParser(
        description="A utility to export project files into a single text file for LLM context.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        '--frontend', 
        action='store_true', 
        help='Only export the frontend directory.'
    )
    parser.add_argument(
        '--backend', 
        action='store_true', 
        help='Only export the backend directory.'
    )
    parser.add_argument(
        '-o', '--output', 
        default='llm_export.txt', 
        help='Name of the output file. (Default: llm_export.txt)'
    )
    parser.add_argument(
        '-e', '--exclude', 
        action='append', 
        default=[],
        help='Add a file or directory name to exclude. Can be used multiple times.'
    )
    parser.add_argument(
        '-v', '--verbose', 
        action='store_true', 
        help='Print the name of each file as it is being exported.'
    )

    args = parser.parse_args()

    # Determine which paths to scan
    paths_to_scan = []
    if args.frontend and not args.backend:
        paths_to_scan.append('frontend')
    elif args.backend and not args.frontend:
        paths_to_scan.append('backend')
    else:
        # Default to both if no flags are specified or if both are specified
        paths_to_scan.extend(['frontend', 'backend'])
        # Also include top-level config files by default
        top_level_files = [f for f in os.listdir('.') if os.path.isfile(f)]
        paths_to_scan.extend(top_level_files)


    # Combine default and user-specified exclusions
    exclude_dirs = DEFAULT_EXCLUDE_DIRS.union(set(args.exclude))
    exclude_files = DEFAULT_EXCLUDE_FILES.union(set(args.exclude))

    print(f"Starting export...")
    print(f"Scanning paths: {', '.join(paths_to_scan)}")
    print(f"Outputting to: {args.output}")

    # Generate the content
    content, count = generate_export_content(paths_to_scan, exclude_dirs, exclude_files, args.verbose)

    # Write the content to the output file
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\nSuccess! Exported {count} files to '{args.output}'.")
    except Exception as e:
        print(f"\nError writing to output file: {e}")


if __name__ == "__main__":
    main()