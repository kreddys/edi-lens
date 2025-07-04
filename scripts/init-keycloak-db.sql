-- This script is a template. All values are provided by the run_app.sh script.

-- Create a dedicated user for Keycloak
CREATE USER :KC_USERNAME_VAR WITH PASSWORD :'KC_PASSWORD_VAR';

-- Create the Keycloak database AND set the new user as its OWNER
CREATE DATABASE :KC_DB_NAME_VAR OWNER :KC_USERNAME_VAR;

-- The GRANT command is no longer needed, as the owner has all privileges.