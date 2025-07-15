# FILE: backend/scripts/preprocess_guide.py
import re
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# This regex is the key. It identifies the start of a new definition.
# It looks for a line starting with a 2-7 character alphanumeric code (like CLM, NM1, 2010AA),
# followed by a space, and then a description that starts with an uppercase letter.
HEADER_PATTERN = re.compile(r"^([A-Z0-9]{2,7})\s+([A-Z][\w\s/()-]+?)(?:\s+Loop)?$")

def sanitize_filename(name: str) -> str:
    """Creates a safe and unique filename from a section title."""
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = re.sub(r'[\s_]+', '_', name)
    return name

def preprocess_guide(guide_path: Path) -> tuple[Path, str]:
    """
    Parses a text implementation guide into atomic chunks for each segment and loop.
    Returns a tuple containing: (path_to_output_directory, table_of_contents_string).
    """
    output_dir = guide_path.parent / f"{guide_path.stem}_chunks"
    output_dir.mkdir(exist_ok=True, parents=True)
    
    logger.info(f"Starting guide preprocessing. Output will be in: {output_dir}")

    with open(guide_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    chunks = []
    current_content = []
    current_title = "Preamble" # Start collecting the Preamble immediately
    
    toc_lines = []
    in_toc_section = False

    for line in lines:
        # A simple, robust check for the start of the final ToC section.
        if line.strip() == "Overview":
            in_toc_section = True
        
        if in_toc_section:
            toc_lines.append(line)
            continue

        match = HEADER_PATTERN.match(line.strip())
        
        if match:
            # A new header is found. This means the previous chunk is complete.
            # Save the completed chunk before starting the new one.
            if current_content:
                chunks.append({"title": current_title, "content": "".join(current_content).strip()})
            
            # Now, start the new chunk.
            segment_code = match.group(1)
            description = match.group(2).strip()
            current_title = f"{segment_code}_{description}"
            current_content = [line] # The new chunk starts with its header line.
        else:
            # This line is not a header, so it's part of the current chunk's content.
            current_content.append(line)

    # After the loop, the very last chunk is still in memory. Save it.
    if current_title and current_content:
        chunks.append({"title": current_title, "content": "".join(current_content).strip()})

    # Write all found chunks to files
    final_chunk_count = 0
    for chunk in chunks:
        # Don't create an empty preamble file if there was no text before the first header.
        if chunk['title'] == "Preamble" and not chunk['content']:
            continue
        
        sanitized_title = sanitize_filename(chunk['title'])
        file_path = output_dir / f"{sanitized_title}.txt"
        file_path.write_text(chunk['content'], encoding='utf-8')
        final_chunk_count += 1

    logger.info(f"Successfully split the guide into {final_chunk_count} chunks.")
    return output_dir, "".join(toc_lines)