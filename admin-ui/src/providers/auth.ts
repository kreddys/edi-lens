import { AuthBindings } from '@refinedev/core';
import { keycloak, getLogger } from '../utils';

const logger = getLogger('AUTH');

export const authProvider: AuthBindings = {
    login: async () => {
        logger.log("Initiating login...");
        await keycloak.login();
        return { success: true };
    },
    logout: async () => {
        logger.log("Initiating logout...");
        localStorage.clear();
        await keycloak.logout({ redirectUri: window.location.origin });
        return { success: true, redirectTo: '/login' };
    },
    check: async () => {
        logger.debug("check() called. Authenticated:", keycloak.authenticated);
        if (keycloak.authenticated && keycloak.token) {
            return { authenticated: true };
        }
        logger.debug("Check failed, returning unauthenticated.");
        return { authenticated: false, logout: true, redirectTo: "/login" };
    },
    getPermissions: async () => {
        const roles = keycloak.tokenParsed?.realm_access?.roles || [];
        logger.debug("getPermissions() called. Roles:", roles);
        return roles;
    },
    getIdentity: async () => {
        logger.debug("getIdentity() called.");
        if (keycloak.tokenParsed) {
            const identity = {
                id: keycloak.tokenParsed.sub,
                name: keycloak.tokenParsed.name,
                groups: keycloak.tokenParsed.groups,
                ...keycloak.tokenParsed,
            };
            logger.debug("Identity found:", identity);
            return identity;
        }
        logger.warn("getIdentity() called, but no token parsed.");
        return null;
    },
    onError: async (error) => {
        logger.error("onError() caught an error:", error);
        // --- THIS IS THE FIX ---
        // Only trigger a logout on a 401 (Unauthorized) error.
        if (error.response?.status === 401) {
            logger.warn("Authentication token is invalid or expired, logging out.");
            return { logout: true, redirectTo: '/login' };
        }

        // For all other errors (including 403 Forbidden), let Refine's
        // notificationProvider show the error message.
        return { error };
    },
};