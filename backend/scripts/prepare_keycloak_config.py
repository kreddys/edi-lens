#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# The unique placeholder we'll use in our template file
PLACEHOLDER = "##KEYCLOAK_BACKEND_CLIENT_SECRET##"

def main():
    """
    Reads the realm template, injects the client secret from the environment,
    and writes the final realm-export.json file.
    """
    client_secret = os.getenv("KEYCLOAK_BACKEND_CLIENT_SECRET")
    if not client_secret:
        print("Error: KEYCLOAK_BACKEND_CLIENT_SECRET environment variable not set.", file=sys.stderr)
        sys.exit(1)

    # --- THIS PATH LOGIC IS UPDATED ---
    # The script is now in backend/scripts, so we need to go up two levels to find the project root.
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent # /backend/scripts -> /backend -> /
    template_path = project_root / "keycloak-config" / "realm-export.template.json"
    output_path = project_root / "keycloak-config" / "realm-export.json"

    try:
        with open(template_path, "r") as f:
            template_content = f.read()
    except FileNotFoundError:
        print(f"Error: Template file not found at {template_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Injecting secret into Keycloak configuration...")
    final_content = template_content.replace(PLACEHOLDER, client_secret)

    with open(output_path, "w") as f:
        f.write(final_content)
    
    print(f"✅ Keycloak configuration successfully written to {output_path}")

if __name__ == "__main__":
    main()