import { AccessControlProvider } from "@refinedev/core";
import { authProvider } from "./auth";

// --- THIS IS THE FIX ---
// This map translates Refine's action names to our specific backend permission names.
const actionPermissionMap: Record<string, string> = {
    list: "read",
    show: "read",
    edit: "update",
    create: "create",
    delete: "delete",
};

export const accessControlProvider: AccessControlProvider = {
    can: async ({ resource, action }) => {
        if (!authProvider.getPermissions) {
            return { can: false, reason: "Access Control is not configured." };
        }
        const permissions = await authProvider.getPermissions();
        if (!Array.isArray(permissions)) {
            return { can: false, reason: "Invalid permissions format" };
        }
        if (permissions.includes("superuser")) {
            return { can: true };
        }

        // Use the map to get the correct permission verb, or default to the action name.
        const permissionAction = actionPermissionMap[action] ?? action;
        const requiredPermission = `${resource}:${permissionAction}`;

        if (permissions.includes(requiredPermission)) {
            return { can: true };
        }

        return { can: false, reason: "You are not authorized to perform this action." };
    },
    options: { buttons: { hideIfUnauthorized: true } },
};