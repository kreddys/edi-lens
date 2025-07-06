import { AccessControlProvider } from "@refinedev/core";
import { authProvider } from "./authProvider";

export const accessControlProvider: AccessControlProvider = {
    // We remove `params` from the destructuring as it's not used.
    can: async ({ resource, action }) => {
        // First, check if the getPermissions method actually exists on our provider.
        if (!authProvider.getPermissions) {
            // If it doesn't, it's safest to deny access.
            return { can: false, reason: "Access Control is not configured." };
        }

        const permissions = await authProvider.getPermissions();

        // Second, ensure the returned permissions are in the expected format (an array).
        if (!Array.isArray(permissions)) {
            console.error("Permissions are not in the expected array format.");
            return { can: false, reason: "Invalid permissions format" };
        }
        
        // Now TypeScript knows `permissions` is a string[] and we can safely use it.
        if (permissions.includes("superuser")) {
            return { can: true };
        }
        
        // The resource name from Refine for our case is "trading-partners"
        // The action can be "create", "edit", "list", "show"
        const requiredPermission = `${resource}:${action}`;
        
        if (permissions.includes(requiredPermission)) {
            return { can: true };
        }

        return { 
            can: false, 
            reason: "You are not authorized to perform this action." 
        };
    },
    options: {
        buttons: {
            hideIfUnauthorized: true,
        },
    },
};