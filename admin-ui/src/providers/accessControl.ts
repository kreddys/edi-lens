import { AccessControlProvider } from "@refinedev/core";
import { authProvider } from "./auth";

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
        const requiredPermission = `${resource}:${action}`;
        if (permissions.includes(requiredPermission)) {
            return { can: true };
        }
        return { can: false, reason: "You are not authorized to perform this action." };
    },
    options: { buttons: { hideIfUnauthorized: true } },
};