#!/usr/bin/env python3
import os
import sys
import time
from keycloak import KeycloakAdmin, KeycloakOpenIDConnection
from keycloak.exceptions import KeycloakGetError, KeycloakPostError

# --- Configuration ---
# Pulled from environment variables set by run_app.sh
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
ADMIN_USER = os.getenv("KEYCLOAK_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")
REALM_NAME = os.getenv("KEYCLOAK_REALM", "edi-lens")
CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "this-is-a-default-secret-change-it")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "edi-lens-client")

# ---
# THE BLUEPRINT: Define the entire Realm Configuration as Code
# ---

# 1. ATOMIC PERMISSIONS (Simple Realm Roles)
ATOMIC_ROLES = [
    {"name": "partner:create", "description": "Can create new trading partners"},
    {"name": "partner:read", "description": "Can read trading partner configurations"},
    {"name": "partner:update", "description": "Can update trading partners"},
    {"name": "partner:delete", "description": "Can delete trading partners"},
    {"name": "validation:run", "description": "Can run EDI validation"},
    {"name": "user:create", "description": "Can invite/create new users in the tenant"},
    {"name": "user:read", "description": "Can view other users in the tenant"},
    {"name": "user:update", "description": "Can update users in the tenant"},
    {"name": "user:delete", "description": "Can remove users from the tenant"},
    {"name": "billing:read", "description": "Can view billing information"},
    {"name": "billing:manage", "description": "Can manage subscriptions and payment"},
    {"name": "superuser:impersonate", "description": "Can impersonate other users"},
    {"name": "superuser:read-all", "description": "Can read data across all tenants"},
]

# 2. BUSINESS ROLES (Composite Realm Roles)
COMPOSITE_ROLES = {
    "tenant-admin": {
        "description": "Full control over a single tenant",
        "children": [
            "partner:create", "partner:read", "partner:update", "partner:delete",
            "validation:run", "user:create", "user:read", "user:update", "user:delete",
            "billing:manage", "billing:read",
        ],
    },
    "tenant-editor": {
        "description": "Can manage trading partners but not users or billing",
        "children": ["partner:create", "partner:read", "partner:update", "partner:delete", "validation:run"],
    },
    "tenant-viewer": {
        "description": "Read-only access to a tenant's data",
        "children": ["partner:read", "validation:run"],
    },
    "superuser": {
        "description": "Global administrator for the entire application",
        "children": ["superuser:impersonate", "superuser:read-all"],
    },
}

# 3. TENANTS (Groups) and their default role assignments
TENANTS = {
    "tenant-a": "tenant-admin",
    "tenant-b": "tenant-viewer",
}

# 4. CLIENTS for the application
CLIENTS = [
    {
        "clientId": KEYCLOAK_CLIENT_ID,
        "name": "EDI Lens API Client",
        "secret": CLIENT_SECRET,
        "enabled": True,
        "clientAuthenticatorType": "client-secret",
        "standardFlowEnabled": True,
        "directAccessGrantsEnabled": True, # For testing and browser flows
        "redirectUris": ["http://localhost:8000/*", "http://localhost:5173/*", "http://127.0.0.1:8000/*", "http://127.0.0.1:5173/*"],
        "webOrigins": ["http://localhost:5173", "http://127.0.0.1:5173"],
    },
]

# 5. USER PERSONAS for testing
USERS = [
    {
        "username": "superuser@edilens.com",
        "password": "password",
        "firstName": "Super", "lastName": "User", "email": "superuser@edilens.com",
        "groups": ["tenant-a", "tenant-b"],
        "realm_roles": ["superuser", "tenant-admin"],
    },
    {
        "username": "admin.a@edilens.com",
        "password": "password",
        "firstName": "Admin", "lastName": "Alpha", "email": "admin.a@edilens.com",
        "groups": ["tenant-a"],
        "realm_roles": [], # Roles are inherited from the group
    },
    {
        "username": "viewer.b@edilens.com",
        "password": "password",
        "firstName": "Viewer", "lastName": "Bravo", "email": "viewer.b@edilens.com",
        "groups": ["tenant-b"],
        "realm_roles": [],
    }
]

# ---
# SCRIPT LOGIC
# ---

def get_keycloak_admin_client() -> KeycloakAdmin:
    """Connect to Keycloak master realm to get an admin client."""
    connection = KeycloakOpenIDConnection(
        server_url=KEYCLOAK_URL, username=ADMIN_USER, password=ADMIN_PASSWORD,
        realm_name="master", user_realm_name="master", client_id="admin-cli",
    )
    return KeycloakAdmin(connection=connection)

def create_or_update_client_scope_mappers(admin_client: KeycloakAdmin):
    """Ensures the necessary token mappers exist on default client scopes."""
    print("\n--- Configuring Client Scope Mappers ---")
    
    # 1. Add Group Membership Mapper
    group_mapper_payload = {
        "name": "groups",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-group-membership-mapper",
        "consentRequired": False,
        "config": {
            "full.path": "false",
            "access.token.claim": "true",
            "id.token.claim": "true",
            "userinfo.token.claim": "true",
            "claim.name": "groups"
        }
    }
    
    # We add this to all default scopes to ensure it's always present
    default_scopes = admin_client.get_default_default_client_scopes()
    for scope in default_scopes:
        scope_id = scope['id']
        try:
            admin_client.add_mapper_to_client_scope(scope_id, group_mapper_payload)
            print(f"  - Added 'groups' mapper to client scope '{scope['name']}'.")
        except KeycloakPostError as e:
            if e.response_code == 409: # Conflict, meaning it already exists
                print(f"  - 'groups' mapper already exists on client scope '{scope['name']}'.")
            else:
                raise e

def main():
    """Main function to configure the Keycloak realm."""
    print("--- Starting Keycloak Realm Setup ---")
    
    admin_client = None
    for i in range(10):
        try:
            admin_client = get_keycloak_admin_client()
            admin_client.get_server_info()
            print("✅ Successfully connected to Keycloak admin endpoint.")
            break
        except Exception:
            print(f"⏳ Keycloak not ready yet (attempt {i+1}/10). Retrying in 5 seconds...")
            time.sleep(5)
    
    if not admin_client:
        print("❌ Could not connect to Keycloak after multiple attempts. Aborting.", file=sys.stderr)
        sys.exit(1)

    print(f"\n--- Ensuring realm '{REALM_NAME}' exists ---")
    try:
        admin_client.get_realm(REALM_NAME)
        print(f"  - Realm '{REALM_NAME}' already exists.")
    except KeycloakGetError as e:
        if e.response_code == 404:
            print(f"  - Realm '{REALM_NAME}' not found. Creating it...")
            admin_client.create_realm(payload={"realm": REALM_NAME, "enabled": True})
            print(f"  - Realm '{REALM_NAME}' created.")
        else:
            raise e

    # Reconnect admin client with new realm context
    admin_client = KeycloakAdmin(
        connection=KeycloakOpenIDConnection(
            server_url=KEYCLOAK_URL,
            username=ADMIN_USER,
            password=ADMIN_PASSWORD,
            realm_name=REALM_NAME,
            user_realm_name="master",
            client_id="admin-cli",
        )
    )


    # Create Roles
    print("\n--- Creating Roles ---")
    all_roles = ATOMIC_ROLES + [{"name": name, "description": d["description"]} for name, d in COMPOSITE_ROLES.items()]
    existing_roles = {role["name"] for role in admin_client.get_realm_roles()}
    for role_payload in all_roles:
        if role_payload["name"] not in existing_roles:
            admin_client.create_realm_role(payload=role_payload)
            print(f"  - Created role: {role_payload['name']}")

    # Assign Composite Roles
    print("\n--- Assigning Composite Roles ---")
    role_map = {role["name"]: role for role in admin_client.get_realm_roles()}
    for name, details in COMPOSITE_ROLES.items():
        parent_role = role_map[name]
        child_roles_to_add = [role_map[child_name] for child_name in details["children"]]
        admin_client.add_composite_realm_roles_to_role(role_name=parent_role['name'], roles=child_roles_to_add)
        print(f"  - Associated {len(child_roles_to_add)} permissions to '{name}'.")

    # Create Groups and Assign Roles
    print("\n--- Creating Tenant Groups & Assigning Roles ---")
    existing_groups = {group["name"]: group for group in admin_client.get_groups()}
    for name, role_to_assign in TENANTS.items():
        group_id = None
        if name not in existing_groups:
            admin_client.create_group(payload={"name": name})
            # Refresh group list after creating
            new_group = next(group for group in admin_client.get_groups() if group["name"] == name)
            group_id = new_group["id"]
            print(f"  - Created group (tenant): {name}")
        else:
            group_id = existing_groups[name]['id']
            print(f"  - Group already exists: {name}")

        
        role_obj = role_map[role_to_assign]
        admin_client.assign_group_realm_roles(group_id=group_id, roles=[role_obj])
        print(f"    - Assigned role '{role_to_assign}' to group '{name}'.")

    # Create Clients
    print("\n--- Creating Clients ---")
    existing_clients = {c['clientId'] for c in admin_client.get_clients()}
    for client_payload in CLIENTS:
        if client_payload['clientId'] not in existing_clients:
            admin_client.create_client(payload=client_payload)
            print(f"  - Created client: {client_payload['clientId']}")
        else:
            print(f"  - Client already exists: {client_payload['clientId']}")

    # Create Users
    print("\n--- Creating Users ---")
    all_groups = admin_client.get_groups()
    group_map = {group["name"]: group for group in all_groups}
    for user_def in USERS:
        if not admin_client.get_users({"username": user_def["username"]}):
            user_id = admin_client.create_user({
                "username": user_def["username"], "email": user_def["email"],
                "firstName": user_def["firstName"], "lastName": user_def["lastName"], "enabled": True,
            })
            print(f"  - Created user: {user_def['username']}")
            admin_client.set_user_password(user_id, user_def["password"], temporary=False)
            print("    - Set permanent password.")

            for group_name in user_def.get("groups", []):
                if group_name in group_map:
                    admin_client.group_user_add(user_id, group_map[group_name]["id"])
                    print(f"    - Added user to group: {group_name}")
            
            if user_def.get("realm_roles"):
                user_roles_to_add = [role_map[role_name] for role_name in user_def["realm_roles"]]
                admin_client.assign_realm_roles(user_id=user_id, roles=user_roles_to_add)
                print(f"    - Assigned realm roles: {user_def['realm_roles']}")
    
    # Configure Mappers
    create_or_update_client_scope_mappers(admin_client)

    print("\n✅ Keycloak Realm Setup Complete!")


if __name__ == "__main__":
    main()