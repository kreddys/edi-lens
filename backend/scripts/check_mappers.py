#!/usr/bin/env python3
from keycloak import KeycloakAdmin, KeycloakOpenIDConnection
import os

# Connect to Keycloak
connection = KeycloakOpenIDConnection(
    server_url='http://keycloak:8080',
    username=os.getenv('KEYCLOAK_ADMIN', 'admin'),
    password=os.getenv('KEYCLOAK_ADMIN_PASSWORD', 'admin'),
    realm_name='master',
    user_realm_name='master',
    client_id='admin-cli',
    timeout=30
)
admin = KeycloakAdmin(connection=connection)
admin.connection.realm_name = 'edi-lens'

# Get clients
clients = admin.get_clients()
backend_client = next((c for c in clients if c['clientId'] == 'edi-lens-backend'), None)

if backend_client:
    print('Backend client ID:', backend_client['id'])
    mappers = admin.get_mappers_from_client(backend_client['id'])
    print('Mappers:', mappers)
else:
    print('Backend client not found')