# FILE: backend/tests/e2e/test_onboarding_e2e.py

import pytest
import pytest_asyncio
import httpx
import uuid
from keycloak import KeycloakAdmin
from keycloak.exceptions import KeycloakGetError

from src.core.config import settings
from tests.e2e.e2e_utils import get_user_token

# This is a highly advanced test. We mark it as 'e2e' and also give it a custom
# 'onboarding' marker so you can run it separately if needed.
pytestmark = [
    pytest.mark.asyncio, 
    pytest.mark.e2e, 
    pytest.mark.onboarding,
    # It's good practice to skip such a complex test by default.
    # You can run it explicitly with: ./run.sh dev:test e2e -m onboarding
    pytest.mark.skip(reason="Full onboarding E2E test is slow and requires Keycloak admin access.")
]

@pytest_asyncio.fixture(scope="function")
async def keycloak_admin_client() -> KeycloakAdmin:
    """Provides an authenticated Keycloak admin client."""
    # This uses the admin credentials from your .env.dev file
    from scripts.setup_keycloak_realm import get_keycloak_admin_client
    
    admin_client = get_keycloak_admin_client()
    admin_client.connection.realm_name = settings.KEYCLOAK_REALM
    return admin_client

@pytest_asyncio.fixture(scope="function")
async def new_tenant_and_user(keycloak_admin_client: KeycloakAdmin):
    """
    E2E Fixture: Creates a new tenant (group), a new user, and assigns the
    user to the tenant with admin permissions. Cleans up everything afterwards.
    """
    admin = keycloak_admin_client
    tenant_name = f"e2e-tenant-{uuid.uuid4()}"
    user_email = f"e2e-user-{uuid.uuid4()}@edilens.com"
    user_password = "password"
    
    # Store IDs for cleanup
    created_ids = {}
    
    try:
        # 1. Create Tenant (Keycloak Group)
        print(f"\n[SETUP] Creating tenant (group): {tenant_name}")
        group_id = admin.create_group(payload={"name": tenant_name})
        created_ids["group"] = group_id

        # 2. Create User for the Tenant
        print(f"[SETUP] Creating user: {user_email}")
        user_id = admin.create_user({
            "email": user_email, "username": user_email,
            "enabled": True, "firstName": "E2E", "lastName": "User"
        })
        admin.set_user_password(user_id, user_password, temporary=False)
        created_ids["user"] = user_id

        # 3. Assign User to Tenant Group
        print(f"[SETUP] Assigning user to group...")
        admin.group_user_add(user_id=user_id, group_id=group_id)

        # 4. Assign "tenant-admin" Role to the User
        # The role should already exist from the main setup script.
        print(f"[SETUP] Assigning 'tenant-admin' role...")
        tenant_admin_role = admin.get_realm_role(role_name="tenant-admin")
        admin.assign_realm_roles(user_id=user_id, roles=[tenant_admin_role])
        
        # Yield the created data to the test function
        yield {
            "tenant_id": tenant_name,
            "user_email": user_email,
            "user_password": user_password
        }

    finally:
        # 5. Teardown (runs after the test is complete)
        print("\n[TEARDOWN] Cleaning up Keycloak entities...")
        if "user" in created_ids:
            try:
                print(f"[TEARDOWN] Deleting user: {user_email}")
                admin.delete_user(user_id=created_ids["user"])
            except KeycloakGetError:
                pass # User might already be gone
        if "group" in created_ids:
            try:
                print(f"[TEARDOWN] Deleting group: {tenant_name}")
                admin.delete_group(group_id=created_ids["group"])
            except KeycloakGetError:
                pass # Group might already be gone

async def test_full_onboarding_and_validation_workflow(
    new_tenant_and_user: dict,
    valid_837p_edi_string: str
):
    """
    Tests the entire user story:
    1. A new tenant and admin user are created.
    2. The new user logs in (gets a token).
    3. The new user creates their first trading partner and profile.
    4. The new user successfully runs a validation using their new profile.
    """
    # --- ARRANGE ---
    # 1. Get the credentials for our newly created user
    tenant_id = new_tenant_and_user["tenant_id"]
    user_email = new_tenant_and_user["user_email"]
    user_password = new_tenant_and_user["user_password"]

    # 2. Log in as the new user to get their token
    print(f"[TEST] Authenticating as new user: {user_email}")
    user_token = await get_user_token(user_email, user_password)
    headers = {"Authorization": f"Bearer {user_token}", "X-Tenant-ID": tenant_id}

    # 3. Use the new user's token to create their first Trading Partner and Profile
    print(f"[TEST] Creating first trading partner in new tenant: {tenant_id}")
    profile_name = "First Claims Profile"
    partner_data = {
        "name": "First E2E Partner",
        "profiles": [{
            "name": profile_name,
            "implementation_guide": "837P",
            "validation_schema_name": "837.5010.X222.A1.json",
        }]
    }
    partner_url = f"http://{settings.BACKEND_HOST}:8000/api/v1/trading-partners"
    async with httpx.AsyncClient() as client:
        response = await client.post(partner_url, headers=headers, json=partner_data)
        assert response.status_code == 201, "New user failed to create their first trading partner."

    # --- ACT ---
    # 4. Now, perform a validation using the newly created profile
    print(f"[TEST] Performing validation with new profile: {profile_name}")
    validation_url = f"http://{settings.BACKEND_HOST}:8000/api/v1/validate"
    payload = {
        "edi_data": valid_837p_edi_string,
        "profile_name": profile_name
    }
    async with httpx.AsyncClient() as client:
        validation_response = await client.post(validation_url, headers=headers, json=payload)

    # --- ASSERT ---
    # 5. Verify that the validation was successful
    assert validation_response.status_code == 200
    validation_data = validation_response.json()
    assert validation_data["valid"] is True
    assert validation_data["matched_profile"] == profile_name
    print(f"[SUCCESS] Full onboarding and validation workflow completed successfully for new tenant '{tenant_id}'.")