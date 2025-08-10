#!/usr/bin/env python3
import os
import sys
import time
from keycloak import KeycloakAdmin, KeycloakOpenIDConnection
from keycloak.exceptions import KeycloakGetError, KeycloakPostError
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration (values loaded from environment) ---
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
ADMIN_USER = os.getenv("KEYCLOAK_ADMIN", "admin")
ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")
REALM_NAME = os.getenv("KEYCLOAK_REALM", "edi-lens")
CLIENT_SECRET = os.getenv("KEYCLOAK_BACKEND_CLIENT_SECRET", "this-is-a-default-secret-change-it")
KEYCLOAK_BACKEND_CLIENT_ID = os.getenv("KEYCLOAK_BACKEND_CLIENT_ID", "edi-lens-backend")
KEYCLOAK_UI_CLIENT_ID = os.getenv("KEYCLOAK_UI_CLIENT_ID", "edi-lens-ui")
REMOTE_HOST = os.getenv("REMOTE_HOST", "localhost")
KEYCLOAK_SFTPGO_CLIENT_SECRET = os.getenv("KEYCLOAK_SFTPGO_CLIENT_SECRET", "default-sftpgo-secret")

# --- Blueprints (unchanged) ---
ATOMIC_ROLES = [
    {"name": "trading-partners:create", "description": "Can create new trading partners"},
    {"name": "trading-partners:read", "description": "Can read trading partner configurations"},
    {"name": "trading-partners:update", "description": "Can update trading partners"},
    {"name": "trading-partners:delete", "description": "Can delete trading partners"},
    {"name": "validation:run", "description": "Can run EDI validation"},
]
COMPOSITE_ROLES = {
    "tenant-admin": {"description": "Full control over a single tenant", "children": ["trading-partners:create", "trading-partners:read", "trading-partners:update", "trading-partners:delete", "validation:run"]},
    "tenant-viewer": {"description": "Read-only access to a tenant's data", "children": ["trading-partners:read"]},
    "superuser": {"description": "Global administrator", "children": ["tenant-admin"]},
}
TENANTS = {"tenant-a": "tenant-admin", "tenant-b": "tenant-viewer"}
redirect_uris = [ f"http://{REMOTE_HOST}:3001/*", f"http://{REMOTE_HOST}:3000/*" ]
web_origins = [ f"http://{REMOTE_HOST}:3001", f"http://{REMOTE_HOST}:3000" ]
if REMOTE_HOST != "localhost":
    redirect_uris.append(f"https://{REMOTE_HOST}/*")
    web_origins.append(f"https://{REMOTE_HOST}")
CLIENTS = [
    {"clientId": KEYCLOAK_UI_CLIENT_ID, "name": "EDI Lens UI", "publicClient": True, "standardFlowEnabled": True, "redirectUris": redirect_uris, "webOrigins": web_origins},
    {"clientId": KEYCLOAK_BACKEND_CLIENT_ID, "name": "EDI Lens Backend", "secret": CLIENT_SECRET, "publicClient": False, "clientAuthenticatorType": "client-secret", "serviceAccountsEnabled": True, "directAccessGrantsEnabled": True}
]
USERS = [
    {"username": "superuser@edilens.com", "password": os.getenv("KC_SUPERUSER_PASSWORD", "password"), "firstName": "Super", "lastName": "User", "groups": ["tenant-a", "tenant-b"], "realm_roles": ["superuser"]},
    {"username": "admin.a@edilens.com", "password": os.getenv("KC_ADMIN_A_PASSWORD", "password"), "firstName": "Admin", "lastName": "Alpha", "groups": ["tenant-a"]},
    {"username": "viewer.b@edilens.com", "password": os.getenv("KC_VIEWER_B_PASSWORD", "password"), "firstName": "Viewer", "lastName": "Bravo", "groups": ["tenant-b"]},
]

def get_keycloak_admin_client() -> KeycloakAdmin:
    connection = KeycloakOpenIDConnection(
        server_url=KEYCLOAK_URL, username=ADMIN_USER, password=ADMIN_PASSWORD,
        realm_name="master", user_realm_name="master", client_id="admin-cli", timeout=30
    )
    return KeycloakAdmin(connection=connection)

def create_or_update_sftpgo_client(admin_client: KeycloakAdmin, existing_clients_map: dict):
    logging.info("\n--- Configuring SFTPGo Client for Keycloak SSO ---")
    
    sftpgo_redirect_uris = [
        f"http://{REMOTE_HOST}:8082/web/oidc/redirect"
    ]

    sftpgo_client_payload = {
        "clientId": "sftpgo",
        "name": "SFTPGo",
        "description": "OIDC client for SFTPGo Admin UI SSO",
        "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "secret": KEYCLOAK_SFTPGO_CLIENT_SECRET,
        "standardFlowEnabled": True,
        "redirectUris": sftpgo_redirect_uris,
        "webOrigins": [f"http://{REMOTE_HOST}:8082"],
        "serviceAccountsEnabled": True,
    }
    
    sftpgo_client = existing_clients_map.get("sftpgo")

    if not sftpgo_client:
        logging.info("  - Creating 'sftpgo' client...")
        admin_client.create_client(payload=sftpgo_client_payload)
    else:
        logging.info("  - 'sftpgo' client already exists. Updating...")
        admin_client.update_client(client_id=sftpgo_client['id'], payload=sftpgo_client_payload)

def configure_client_mappers(admin_client: KeycloakAdmin, existing_clients_map: dict):
    logging.info("\n--- Configuring Client Mappers ---")
    
    # Mapper to add user groups (tenants) to the token
    group_mapper = {
        "name": "groups", "protocol": "openid-connect", "protocolMapper": "oidc-group-membership-mapper",
        "config": {"full.path": "false", "access.token.claim": "true", "id.token.claim": "true", "claim.name": "groups"}
    }
    
    # Mapper to add the backend's client ID to the token's audience
    audience_mapper = {
        "name": "backend-audience",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-audience-mapper",
        "config": {
            "id.token.claim": "false",
            "access.token.claim": "true",
            "included.client.audience": KEYCLOAK_BACKEND_CLIENT_ID,
        },
    }

    ui_client = existing_clients_map.get(KEYCLOAK_UI_CLIENT_ID)
    backend_client = existing_clients_map.get(KEYCLOAK_BACKEND_CLIENT_ID)
    
    if not ui_client:
        logging.error(f"  - ERROR: Could not find UI client '{KEYCLOAK_UI_CLIENT_ID}' to add mappers.")
        return
        
    if not backend_client:
        logging.error(f"  - ERROR: Could not find backend client '{KEYCLOAK_BACKEND_CLIENT_ID}' to add mappers.")
        return

    # Add group mapper to UI client
    try:
        admin_client.add_mapper_to_client(ui_client['id'], group_mapper)
        logging.info(f"  - Added 'groups' mapper to UI client.")
    except KeycloakPostError as e:
        if e.response_code == 409:
            logging.info(f"  - Mapper 'groups' already exists on UI client.")
        else:
            raise

    # Add group mapper to backend client
    try:
        admin_client.add_mapper_to_client(backend_client['id'], group_mapper)
        logging.info(f"  - Added 'groups' mapper to backend client.")
    except KeycloakPostError as e:
        if e.response_code == 409:
            logging.info(f"  - Mapper 'groups' already exists on backend client.")
        else:
            raise

    # Add audience mapper to backend client
    try:
        admin_client.add_mapper_to_client(backend_client['id'], audience_mapper)
        logging.info(f"  - Added 'backend-audience' mapper to backend client.")
    except KeycloakPostError as e:
        if e.response_code == 409:
            logging.info(f"  - Mapper 'backend-audience' already exists on backend client.")
        else:
            raise

def main():
    logging.info("--- Starting Keycloak Realm Setup ---")
    admin_client = None
    for i in range(15):
        try:
            logging.info(f"Connecting to Keycloak admin API (attempt {i+1}/15)...")
            admin_client = get_keycloak_admin_client()
            admin_client.get_server_info()
            logging.info("✅ Successfully connected.")
            break
        except Exception as e:
            logging.warning(f"⏳ Keycloak not ready. Retrying in 5s... (Error: {e})")
            time.sleep(5)
    if not admin_client:
        logging.error("❌ Could not connect to Keycloak. Aborting.")
        sys.exit(1)

    logging.info(f"\n--- Ensuring realm '{REALM_NAME}' exists ---")
    try:
        admin_client.get_realm(REALM_NAME)
        logging.info(f"  - Realm '{REALM_NAME}' already exists.")
    except KeycloakGetError:
        logging.info(f"  - Realm '{REALM_NAME}' not found. Creating...")
        admin_client.create_realm(payload={"realm": REALM_NAME, "enabled": True})
        logging.info(f"  - Realm '{REALM_NAME}' created.")

    admin_client.connection.realm_name = REALM_NAME

    logging.info("\n--- Creating/Updating Roles ---")
    all_role_defs = ATOMIC_ROLES + [{"name": name, **details} for name, details in COMPOSITE_ROLES.items()]
    existing_roles_map = {role["name"]: role for role in admin_client.get_realm_roles()}
    for role_def in all_role_defs:
        if role_def["name"] not in existing_roles_map:
            admin_client.create_realm_role(payload={"name": role_def["name"], "description": role_def.get("description", "")})

    logging.info("\n--- Assigning Composite Roles ---")
    all_roles_map = {role["name"]: role for role in admin_client.get_realm_roles()}
    for parent_name, details in COMPOSITE_ROLES.items():
        parent_role = all_roles_map[parent_name]
        child_roles = [all_roles_map[child_name] for child_name in details.get("children", [])]
        if child_roles:
            admin_client.add_composite_realm_roles_to_role(role_name=parent_role['name'], roles=child_roles)

    logging.info("\n--- Creating Tenant Groups & Assigning Roles ---")
    existing_groups_map = {group["name"]: group for group in admin_client.get_groups()}
    for group_name, role_name in TENANTS.items():
        if group_name not in existing_groups_map:
            group_id = admin_client.create_group(payload={"name": group_name})
        else:
            group_id = existing_groups_map[group_name]['id']
        role_to_assign = all_roles_map.get(role_name)
        if role_to_assign:
            admin_client.assign_group_realm_roles(group_id=group_id, roles=[role_to_assign])

    logging.info("\n--- Creating/Updating Clients (edi-lens-ui, edi-lens-backend) ---")
    # First, get a preliminary list of clients
    initial_clients_map = {c['clientId']: c for c in admin_client.get_clients()}
    for client_payload in CLIENTS:
        client_id = client_payload['clientId']
        if client_id not in initial_clients_map:
            logging.info(f"  - Creating client '{client_id}'...")
            admin_client.create_client(payload=client_payload)
        else:
            logging.info(f"  - Client '{client_id}' already exists. Updating...")
            internal_id = initial_clients_map[client_id]['id']
            admin_client.update_client(client_id=internal_id, payload=client_payload)

    # Now, get an updated list that is guaranteed to contain our main clients
    all_clients_list = admin_client.get_clients()
    existing_clients_map = {c['clientId']: c for c in all_clients_list}
    
    # Now, create/update the SFTPGo client using the fresh list
    create_or_update_sftpgo_client(admin_client, existing_clients_map)

    # Configure client mappers
    configure_client_mappers(admin_client, existing_clients_map)

if __name__ == "__main__":
    main()