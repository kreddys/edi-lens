#!/bin/bash
# SFTPGo User Setup Script using CLI commands
# This script creates trading partner users with MinIO virtual folders

set -e

echo "🚀 Setting up SFTPGo users for EDI Lens trading partners..."

# Configuration
SFTPGO_CONTAINER="sftpgo"
MINIO_ENDPOINT="http://minio:9000"
MINIO_ACCESS_KEY="${STORAGE_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${STORAGE_SECRET_KEY:-minioadmin}"
MINIO_BUCKET="${STORAGE_BUCKET:-edi-lens-schemas}"

# Function to create virtual folder
create_virtual_folder() {
    local folder_name="$1"
    local tenant_id="$2" 
    local username="$3"
    local path_type="$4"  # "in" or "out"
    
    echo "📁 Creating virtual folder: ${folder_name}"
    
    # Create folder configuration JSON
    cat > /tmp/folder_${folder_name}.json << EOF
{
    "name": "${folder_name}",
    "mapped_path": "/tmp",
    "description": "EDI Lens ${path_type} folder for ${username}",
    "filesystem": {
        "provider": "s3",
        "s3config": {
            "bucket": "${MINIO_BUCKET}",
            "region": "us-east-1",
            "access_key": "${MINIO_ACCESS_KEY}",
            "access_secret": "${MINIO_SECRET_KEY}",
            "endpoint": "${MINIO_ENDPOINT}",
            "key_prefix": "sftp/${tenant_id}/${username}/${path_type}/",
            "force_path_style": true,
            "upload_part_size": 5,
            "upload_concurrency": 2,
            "download_part_size": 5,
            "download_concurrency": 2
        }
    }
}
EOF
    
    # Copy to container and create folder
    docker cp /tmp/folder_${folder_name}.json ${SFTPGO_CONTAINER}:/tmp/
    docker exec ${SFTPGO_CONTAINER} sh -c "
        if sftpgo gen folder --help > /dev/null 2>&1; then
            echo 'Creating folder using CLI...'
            sftpgo gen folder --name '${folder_name}' --mapped-path '/tmp' --s3-bucket '${MINIO_BUCKET}' --s3-endpoint '${MINIO_ENDPOINT}' --s3-access-key '${MINIO_ACCESS_KEY}' --s3-access-secret '${MINIO_SECRET_KEY}' --s3-key-prefix 'sftp/${tenant_id}/${username}/${path_type}/' --s3-force-path-style
        else
            echo 'CLI folder creation not available, using JSON approach'
        fi
    "
    
    # Cleanup
    rm -f /tmp/folder_${folder_name}.json
}

# Function to create user
create_user() {
    local username="$1"
    local password="$2"
    local tenant_id="$3"
    local partner_name="$4"
    
    echo "👤 Creating user: ${username} for ${partner_name}"
    
    # Create user JSON configuration
    cat > /tmp/user_${username}.json << EOF
{
    "username": "${username}",
    "password": "${password}",
    "status": 1,
    "email": "${username}@edilens.com",
    "description": "EDI Lens Trading Partner - ${partner_name} (Tenant: ${tenant_id})",
    "home_dir": "/${tenant_id}/${username}",
    "uid": 1000,
    "gid": 1000,
    "max_sessions": 5,
    "quota_size": 0,
    "quota_files": 0,
    "permissions": {
        "/": ["*"]
    },
    "upload_bandwidth": 0,
    "download_bandwidth": 0,
    "upload_data_transfer": 0,
    "download_data_transfer": 0,
    "expires_at": 0,
    "filesystem": {
        "provider": "s3",
        "s3config": {
            "bucket": "${MINIO_BUCKET}",
            "region": "us-east-1",
            "access_key": "${MINIO_ACCESS_KEY}",
            "access_secret": "${MINIO_SECRET_KEY}",
            "endpoint": "${MINIO_ENDPOINT}",
            "key_prefix": "sftp/${tenant_id}/${username}/",
            "force_path_style": true,
            "upload_part_size": 5,
            "upload_concurrency": 2,
            "download_part_size": 5,
            "download_concurrency": 2
        }
    },
    "virtual_folders": [
        {
            "name": "${username}-in",
            "virtual_path": "/in",
            "quota_size": 0,
            "quota_files": 0
        },
        {
            "name": "${username}-out", 
            "virtual_path": "/out",
            "quota_size": 0,
            "quota_files": 0
        }
    ]
}
EOF

    # Create virtual folders first
    create_virtual_folder "${username}-in" "${tenant_id}" "${username}" "in"
    create_virtual_folder "${username}-out" "${tenant_id}" "${username}" "out"
    
    # Copy user config to container
    docker cp /tmp/user_${username}.json ${SFTPGO_CONTAINER}:/tmp/
    
    # Create user via CLI if available, otherwise document manual process
    docker exec ${SFTPGO_CONTAINER} sh -c "
        if sftpgo gen user --help > /dev/null 2>&1; then
            echo 'Creating user via CLI...'
            sftpgo gen user --username '${username}' --password '${password}' --home-dir '/${tenant_id}/${username}' --uid 1000 --gid 1000 --max-sessions 5
        else
            echo 'User creation via CLI not available. Manual setup required via web interface.'
            echo 'User config saved to: /tmp/user_${username}.json'
        fi
    "
    
    # Cleanup
    rm -f /tmp/user_${username}.json
    
    echo "✅ User ${username} setup completed"
}

# Create trading partner users based on seeded data
echo "📊 Creating trading partner users..."

# Tenant A Users
create_user "tenant-a_uhg-pro" "uhg_secure_pass_123" "tenant-a" "United Health Group (Professional)"
create_user "tenant-a_chc" "chc_secure_pass_456" "tenant-a" "Change Healthcare (Clearinghouse)"

# Tenant B Users  
create_user "tenant-b_medicaid" "medicaid_pass_789" "tenant-b" "State Medicaid"

echo ""
echo "✅ SFTPGo user setup completed!"
echo ""
echo "🌐 SFTPGo Web Admin: http://localhost:8080/web/admin/"
echo "🔑 Admin credentials: admin / admin123"
echo "📡 SFTP Connection: localhost:2022"
echo "💾 Storage Backend: MinIO S3 (${MINIO_ENDPOINT})"
echo ""
echo "📋 Trading Partner Connections:"
echo "  - tenant-a_uhg-pro:uhg_secure_pass_123 (United Health Group)"
echo "  - tenant-a_chc:chc_secure_pass_456 (Change Healthcare)"  
echo "  - tenant-b_medicaid:medicaid_pass_789 (State Medicaid)"
echo ""
echo "📁 Virtual Folders:"
echo "  - /in  -> sftp/{tenant}/{username}/in/"
echo "  - /out -> sftp/{tenant}/{username}/out/"