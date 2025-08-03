#!/bin/bash
# Multi-Tenant SFTP Server Initialization Script
# Sets up tenant-isolated directory structure for SFTP partners

set -e

echo "=== EDI Lens Multi-Tenant SFTP Server Initialization ==="

# Create the main tenants directory
TENANTS_ROOT="/sftp/tenants"
mkdir -p "$TENANTS_ROOT"
chown root:root "$TENANTS_ROOT"
chmod 755 "$TENANTS_ROOT"

# Create groups for SFTP users
groupadd -f sftpusers
groupadd -f tenantusers

echo "Tenants root directory created: $TENANTS_ROOT"

# Function to create tenant directory structure
create_tenant_structure() {
    local tenant_id="$1"
    local tenant_dir="$TENANTS_ROOT/$tenant_id"
    
    echo "Creating tenant structure for: $tenant_id"
    
    # Create tenant root directory (owned by root for security)
    mkdir -p "$tenant_dir"
    chown root:root "$tenant_dir"
    chmod 755 "$tenant_dir"
    
    echo "Tenant directory created: $tenant_dir"
}

# Function to create partner directory within a tenant
create_partner_structure() {
    local tenant_id="$1"
    local partner_name="$2"
    local partner_password="$3"
    
    local tenant_dir="$TENANTS_ROOT/$tenant_id"
    local partner_dir="$tenant_dir/$partner_name"
    
    echo "Creating partner structure: $tenant_id/$partner_name"
    
    # Ensure tenant directory exists
    if [ ! -d "$tenant_dir" ]; then
        create_tenant_structure "$tenant_id"
    fi
    
    # Create partner root directory (owned by root for chroot security)
    mkdir -p "$partner_dir"
    chown root:root "$partner_dir"
    chmod 755 "$partner_dir"
    
    # Create in and out directories that the partner can access
    mkdir -p "$partner_dir/in"
    mkdir -p "$partner_dir/out"
    
    # Create unique username for this tenant-partner combination
    local username="${tenant_id}_${partner_name}"
    
    # Create the partner user if it doesn't exist
    if ! id "$username" &>/dev/null; then
        # Set home directory to the partner directory for chroot
        # Use /usr/sbin/nologin instead of /bin/false for SFTP compatibility
        useradd -d "$partner_dir" -s /usr/sbin/nologin -G tenantusers,sftpusers "$username"
        echo "$username:$partner_password" | chpasswd
        echo "Created partner user: $username"
    fi
    
    # Set proper ownership for partner directories
    # Partner can read/write in 'in' and 'out' directories only
    chown -R "$username:tenantusers" "$partner_dir/in" "$partner_dir/out"
    chmod 755 "$partner_dir/in" "$partner_dir/out"
    
    # Create welcome file
    cat > "$partner_dir/in/README.txt" << EOF
Welcome to EDI Lens SFTP Server
Tenant: $tenant_id
Partner: $partner_name

Upload your EDI files to this 'in' directory.
Processed acknowledgments will be placed in the 'out' directory.

You have access only to:
- in/  (for uploading files)
- out/ (for downloading responses)
EOF
    chown "$username:tenantusers" "$partner_dir/in/README.txt"
    
    echo "Partner structure created: $username -> $partner_dir"
}

# Create demo tenant structures for testing
echo "Creating demo tenant structures..."

# Tenant A with 2 partners
create_tenant_structure "tenant-a"
create_partner_structure "tenant-a" "partner-1" "pass123"
create_partner_structure "tenant-a" "partner-2" "pass456"

# Tenant B with 1 partner  
create_tenant_structure "tenant-b"
create_partner_structure "tenant-b" "partner-3" "pass789"

# Configure SSH chroot for tenant users
echo "Configuring SSH chroot for tenant isolation..."

# Add chroot configuration to SSH config
cat >> /config/sshd/sshd_config_custom << 'EOF'

# Multi-tenant SFTP chroot configuration
Match Group sftpusers
    ChrootDirectory %h
    ForceCommand internal-sftp
    AllowTcpForwarding no
    X11Forwarding no
    PermitTunnel no
EOF

echo "SSH chroot configuration added."

echo "=== Multi-Tenant SFTP Server initialization completed ==="
echo ""
echo "Demo tenant structures created:"
echo "  tenant-a_partner-1 (password: pass123)"
echo "  tenant-a_partner-2 (password: pass456)" 
echo "  tenant-b_partner-3 (password: pass789)"
echo ""
echo "Connection details:"
echo "  Host: localhost"
echo "  Port: 2222"
echo "  Example: sftp -P 2222 tenant-a_partner-1@localhost"
echo ""
echo "=== Ready for multi-tenant partner connections ==="