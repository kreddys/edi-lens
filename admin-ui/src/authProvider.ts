import Keycloak from 'keycloak-js';
import { AuthBindings } from '@refinedev/core';

const keycloak = new Keycloak({
    url: import.meta.env.VITE_KEYCLOAK_URL,
    realm: import.meta.env.VITE_KEYCLOAK_REALM,
    clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID,
});

export const authProvider: AuthBindings = {
    login: async () => {
        const url = keycloak.createLoginUrl();
        window.location.href = url;
        return { success: false };
    },
    logout: async () => {
        localStorage.clear();
        const url = keycloak.createLogoutUrl();
        window.location.href = url;
        return { success: false };
    },
    check: async () => {
        try {
            const authenticated = await keycloak.init({ onLoad: 'login-required' });
            if (authenticated && keycloak.token) {
                localStorage.setItem("keycloak_token", keycloak.token);
                return { authenticated: true };
            }
        } catch (error) {
            console.error("Authentication check failed", error);
        }
        return { authenticated: false, logout: true, redirectTo: "/login" };
    },
    getPermissions: async () => {
        return keycloak.tokenParsed?.realm_access?.roles || [];
    },
    getIdentity: async () => {
        if (keycloak.tokenParsed) {
            return {
                id: keycloak.tokenParsed.sub,
                name: keycloak.tokenParsed.name,
                groups: keycloak.tokenParsed.groups,
            };
        }
        return null;
    },
    onError: async (error) => {
        if (error.response?.status === 401 || error.response?.status === 403) {
            return { logout: true };
        }
        return { error };
    },
};