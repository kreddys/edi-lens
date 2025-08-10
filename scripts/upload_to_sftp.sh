#!/bin/bash
# SFTP Upload Script for EDI Lens Testing

# Default values
DEFAULT_USER="test125"
DEFAULT_PASSWORD="test125"

# Check if file argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <file_to_upload> [username] [password]"
    echo "Example: $0 test-file.edi test125 test125"
    exit 1
fi

# Get file to upload
FILE_TO_UPLOAD="$1"

# Get username and password (use defaults if not provided)
SFTP_USER="${2:-$DEFAULT_USER}"
SFTP_PASSWORD="${3:-$DEFAULT_PASSWORD}"

# Check if file exists
if [ ! -f "$FILE_TO_UPLOAD" ]; then
    echo "Error: File '$FILE_TO_UPLOAD' not found"
    exit 1
fi

# Upload file via SFTP
echo "Uploading $FILE_TO_UPLOAD to SFTP server as user $SFTP_USER..."
sshpass -p "$SFTP_PASSWORD" sftp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -P 2022 "$SFTP_USER"@localhost << EOF
put "$FILE_TO_UPLOAD" /in/$(basename "$FILE_TO_UPLOAD")
quit
EOF

echo "Upload complete!"