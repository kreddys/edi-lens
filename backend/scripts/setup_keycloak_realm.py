#!/usr/bin/env python3
import os
import sys
import time
from keycloak import KeycloakAdmin, KeycloakOpenIDConnection
from keycloak.exceptions import KeycloakGetError, KeycloakPostError

# --- Configuration (unchanged) ---
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
ADMIN_USER = os.getenv("KEYCLOAK_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")
REALM_NAME = os.getenv("KEYCLOAK_REALM", "edi-lens")
CLIENT_SECRET = os.getenv("KEYCLOAK_BACKEND_CLIENT_SECRET", "this-is-a-default-secret-change-it")
KEYCLOAK_BACKEND_CLIENT_ID = os.getenv("KEYCLOAK_BACKEND_CLIENT_ID", "edi-lens-backend")
KEYCLOAK_UI_CLIENT_ID = os.getenv("KEYCLOAK_UI_CLIENT_ID", "edi-lens-ui")

# --- Blueprint Definitions (unchanged) ---
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
COMPOSITE_ROLES = {
    "tenant-admin": {"description": "Full control over a single tenant", "children": ["partner:create", "partner:read", "partner:update", "partner:delete", "validation:run", "user:create", "user:read", "user:update", "user:delete", "billing:manage", "billing:read"]},
    "tenant-editor": {"description": "Can manage trading partners but not users or billing", "children": ["partner:create", "partner:read", "partner:update", "partner:delete", "validation:run"]},
    "tenant-viewer": {"description": "Read-only access to a tenant's data", "children": ["partner:read", "validation:run"]},
    "superuser": {"description": "Global administrator for the entire application", "children": ["superuser:impersonate", "superuser:read-all"]},
}
TENANTS = {"tenant-a": "tenant-admin", "tenant-b": "tenant-viewer"}
# --- THIS IS PART OF THE FIX ---
# Add our new 'basic' scope to the list of default scopes for our client.

CLIENTS = [
    {
        "clientId": KEYCLOAK_UI_CLIENT_ID,
        "name": "EDI Lens UI",
        "publicClient": True, # Public client, no secret
        "standardFlowEnabled": True,
        "directAccessGrantsEnabled": False, # Not needed for UI
        "redirectUris": ["http://localhost:3000/*"],
        "webOrigins": ["http://localhost:3000"],
    },
    {
        "clientId": KEYCLOAK_BACKEND_CLIENT_ID,
        "name": "EDI Lens Backend",
        "secret": os.getenv("KEYCLOAK_BACKEND_CLIENT_SECRET"),
        "publicClient": False, # Confidential client
        "clientAuthenticatorType": "client-secret",
        "directAccessGrantsEnabled": True, # For testing
        "serviceAccountsEnabled": True, # Good practice for backend clients
    }
]

USERS = [
    {"username": "superuser@edilens.com", "password": "password", "firstName": "Super", "lastName": "User", "email": "superuser@edilens.com", "groups": ["tenant-a", "tenant-b"], "realm_roles": ["superuser", "tenant-admin"]},
    {"username": "admin.a@edilens.com", "password": "password", "firstName": "Admin", "lastName": "Alpha", "email": "admin.a@edilens.com", "groups": ["tenant-a"], "realm_roles": []},
    {"username": "viewer.b@edilens.com", "password": "password", "firstName": "Viewer", "lastName": "Bravo", "email": "viewer.b@edilens.com", "groups": ["tenant-b"], "realm_roles": []}
]


# --- SCRIPT LOGIC ---

def get_keycloak_admin_client() -> KeycloakAdmin:
    connection = KeycloakOpenIDConnection(
        server_url=KEYCLOAK_URL, username=ADMIN_USER, password=ADMIN_PASSWORD,
        realm_name="master", user_realm_name="master", client_id="admin-cli",
    )
    return KeycloakAdmin(connection=connection)

# --- THIS IS THE FIX ---
def create_or_update_client_scope_mappers(admin_client: KeycloakAdmin):
    """Ensures the necessary token mappers and scopes exist."""
    print("\n--- Configuring Client Scopes and Mappers ---")

    # 1. Define the new 'basic' client scope
    basic_scope_payload = {
        "name": "basic",
        "description": "Scope for basic OIDC claims like sub.",
        "protocol": "openid-connect",
        "attributes": {
            "include.in.token.scope": "false",
            "display.on.consent.screen": "false"
        }
    }
    
    # Create the 'basic' scope if it doesn't exist
    basic_scope_id = None
    existing_scopes = admin_client.get_client_scopes()
    basic_scope = next((s for s in existing_scopes if s.get('name') == 'basic'), None)

    if not basic_scope:
        print("  - 'basic' client scope not found, creating it...")
        basic_scope_id = admin_client.create_client_scope(basic_scope_payload, skip_exists=True)
    else:
        print("  - 'basic' client scope already exists.")
        basic_scope_id = basic_scope['id']

    # 2. Define the 'sub' mapper for the 'basic' scope
    sub_mapper_payload = {
        "name": "sub",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-sub-mapper",  # The correct mapper type
        "consentRequired": False,
        "config": {
            "id.token.claim": "true",
            "access.token.claim": "true"
        }
    }

    # Add the 'sub' mapper to the 'basic' scope
    try:
        admin_client.add_mapper_to_client_scope(basic_scope_id, sub_mapper_payload)
        print("  - Added 'sub' mapper to 'basic' scope.")
    except KeycloakPostError as e:
        if e.response_code == 409: # Conflict
            print("  - 'sub' mapper already exists in 'basic' scope.")
        else:
            raise e

    # 3. Add other required mappers (groups, audience) to the 'profile' scope
    profile_scope = next((cs for cs in existing_scopes if cs['name'] == 'profile'), None)
    if not profile_scope:
        print("❌ Could not find 'profile' client scope.")
        return
    profile_scope_id = profile_scope['id']

    group_mapper = {
        "name": "groups", "protocol": "openid-connect", "protocolMapper": "oidc-group-membership-mapper",
        "config": {"full.path": "false", "access.token.claim": "true", "claim.name": "groups"}
    }
    audience_mapper = {
        "name": "audience-mapper", "protocol": "openid-connect", "protocolMapper": "oidc-audience-mapper",
        "config": {"access.token.claim": "true", "included.client.audience": KEYCLOAK_BACKEND_CLIENT_ID}
    }

    for mapper in [group_mapper, audience_mapper]:
        try:
            admin_client.add_mapper_to_client_scope(profile_scope_id, mapper)
            print(f"  - Added '{mapper['name']}' mapper to 'profile' scope.")
        except KeycloakPostError as e:
            if e.response_code == 409: # Conflict
                pass
            else:
                raise e


def main():
    print("--- Starting Keycloak Realm Setup ---")
    
    admin_client = None
    for i in range(10):
        try:
            admin_client = get_keycloak_admin_client()
            admin_client.get_server_info()
            print("✅ Successfully connected to Keycloak admin endpoint.")
            break
        except Exception as e:
            print(f"⏳ Keycloak not ready yet (attempt {i+1}/10). Retrying in 5 seconds... ({e})")
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

    admin_client.connection.realm_name = REALM_NAME

    create_or_update_client_scope_mappers(admin_client)

    print("\n--- Creating Roles ---")
    all_roles = ATOMIC_ROLES + [{"name": name, "description": d["description"]} for name, d in COMPOSITE_ROLES.items()]
    existing_roles = {role["name"] for role in admin_client.get_realm_roles()}
    for role_payload in all_roles:
        if role_payload["name"] not in existing_roles:
            admin_client.create_realm_role(payload=role_payload)

    print("\n--- Assigning Composite Roles ---")
    role_map = {role["name"]: role for role in admin_client.get_realm_roles()}
    for name, details in COMPOSITE_ROLES.items():
        parent_role = role_map[name]
        child_roles_to_add = [role_map[child_name] for child_name in details["children"]]
        admin_client.add_composite_realm_roles_to_role(role_name=parent_role['name'], roles=child_roles_to_add)

    print("\n--- Creating Tenant Groups & Assigning Roles ---")
    existing_groups = {group["name"]: group for group in admin_client.get_groups()}
    for name, role_to_assign in TENANTS.items():
        group_id = None
        if name not in existing_groups:
            group_id = admin_client.create_group(payload={"name": name})
        else:
            group_id = existing_groups[name]['id']
        role_obj = role_map[role_to_assign]
        admin_client.assign_group_realm_roles(group_id=group_id, roles=[role_obj])

    print("\n--- Creating/Updating Clients ---")
    existing_clients = {c['clientId']: c for c in admin_client.get_clients()}
    for client_payload in CLIENTS:
        client_id_name = client_payload['clientId']
        if client_id_name not in existing_clients:
            admin_client.create_client(payload=client_payload)
        else:
            internal_id = existing_clients[client_id_name]['id']
            admin_client.update_client(client_id=internal_id, payload=client_payload)

    print("\n--- Creating Users ---")
    all_groups = admin_client.get_groups()
    group_map = {group["name"]: group["id"] for group in all_groups}
    for user_def in USERS:
        users = admin_client.get_users({"username": user_def["username"]})
        if not users:
            user_id = admin_client.create_user({"username": user_def["username"], "email": user_def["email"], "firstName": user_def["firstName"], "lastName": user_def["lastName"], "enabled": True})
            admin_client.set_user_password(user_id, user_def["password"], temporary=False)
        else:
            user_id = users[0]['id']
        for group_name in user_def.get("groups", []):
            if group_name in group_map:
                try:
                    admin_client.group_user_add(user_id, group_map[group_name])
                except KeycloakPostError as e:
                    if e.response_code != 409: raise e
        if user_def.get("realm_roles"):
            user_roles_to_add = [role_map[role_name] for role_name in user_def["realm_roles"]]
            admin_client.assign_realm_roles(user_id=user_id, roles=user_roles_to_add)
    
    print("\n✅ Keycloak Realm Setup Complete!")


if __name__ == "__main__":
    main()