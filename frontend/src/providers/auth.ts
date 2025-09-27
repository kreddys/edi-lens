/**
 * Simple auth provider for testing purposes
 * In a real application, this would integrate with your authentication system
 */
export const authProvider = {
    login: async () => {
        return {
            success: true,
            redirectTo: "/",
        };
    },
    logout: async () => {
        return {
            success: true,
            redirectTo: "/login",
        };
    },
    check: async () => {
        return {
            authenticated: true,
        };
    },
    onError: async () => {
        return { error: null };
    },
    getPermissions: async () => {
        return null;
    },
    getIdentity: async () => {
        return {
            id: "test-user",
            name: "Test User",
        };
    },
};