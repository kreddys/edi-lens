import { keycloakAuthProvider } from 'ra-keycloak';
import Keycloak, { KeycloakTokenParsed } from 'keycloak-js';
import { AuthProvider } from 'react-admin';

// The keycloak-js instance.
const keycloak = new Keycloak({
    url: import.meta.env.VITE_KEYCLOAK_URL,
    realm: import.meta.env.VITE_KEYCLOAK_REALM,
    clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID,
});

// The base provider from the library, configured correctly.
const baseAuthProvider = keycloakAuthProvider(keycloak, {
    // --- THIS IS THE FIX ---
    // The onLoad option must be passed inside initOptions.
    initOptions: {
        onLoad: 'login-required',
    },
});

interface UserProfile extends KeycloakTokenParsed {
    id: string;
    fullName?: string;
    groups?: string[];
}

// Wrap the base provider to add our custom logic
export const authProvider: AuthProvider = {
    ...baseAuthProvider,
    
    // We override getIdentity to provide the user's groups to the UI.
    getIdentity: async () => {
        // First, ensure the user is authenticated. This will also initialize the keycloak instance.
        try {
            await baseAuthProvider.checkAuth({}); // Pass empty params to match interface
        } catch (error) {
            // Let the base provider handle the redirect on auth error.
            return Promise.reject(error);
        }
        
        if (keycloak.tokenParsed) {
             const profile: UserProfile = {
                id: keycloak.tokenParsed.sub || '',
                fullName: keycloak.tokenParsed.name,
                groups: keycloak.tokenParsed.groups || [],
            };
            return Promise.resolve(profile);
        }

        // Fallback that should rarely be hit.
        if (baseAuthProvider.getIdentity) {
            return baseAuthProvider.getIdentity();
        }

        return Promise.reject('Could not retrieve user identity.');
    },

    // We override logout to clear our custom data.
    logout: async (params?: any) => {
        localStorage.removeItem('selected_tenant');
        // Let the base provider handle the actual logout and redirect.
        return baseAuthProvider.logout(params);
    },
};