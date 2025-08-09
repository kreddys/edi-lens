// FILE: admin-ui/src/providers/data.ts

import simpleRestProvider from "@refinedev/simple-rest";
import { DataProvider } from "@refinedev/core";
import axios from "axios";
import { keycloak, getLogger } from '../utils';

const logger = getLogger('DATA');
const axiosInstance = axios.create();

axiosInstance.interceptors.request.use(
    (config) => {
        const selectedTenant = localStorage.getItem('selected_tenant');
        if (keycloak.authenticated && keycloak.token) {
            config.headers.Authorization = `Bearer ${keycloak.token}`;
        }
        if (selectedTenant) {
            config.headers['X-Tenant-ID'] = selectedTenant;
        } else {
            if (config.url && !config.url.includes("/schemas")) {
                logger.warn('No tenant selected. Halting API request to a tenant-specific endpoint.');
                return Promise.reject(new axios.Cancel('No tenant selected'));
            }
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// --- THIS IS THE FIX (Part 1) ---
// Initialize the provider with only the required 2 arguments.
const baseDataProvider = simpleRestProvider(
    import.meta.env.VITE_API_URL, 
    axiosInstance
);
// --- END OF FIX ---

export const dataProvider: DataProvider = {
    ...baseDataProvider,

    // --- THIS IS THE FIX (Part 2) ---
    // Override the `update` method to use `axiosInstance.put` directly.
    // This is the correct way to force a PUT request for all update operations.
    update: async ({ resource, id, variables }) => {
        const url = `${import.meta.env.VITE_API_URL}/${resource}/${id}`;
        const { data } = await axiosInstance.put(url, variables);
        return { data };
    },
    // --- END OF FIX ---

    // The special 'create' logic for copying schemas remains the same.
    create: async ({ resource, variables }) => {
        const copyMatch = resource.match(/^schemas\/(.+)\/copy$/);
        
        if (copyMatch) {
            const baseSchemaName = copyMatch[1];
            const url = `${import.meta.env.VITE_API_URL}/schemas/${baseSchemaName}/copy`;
            const { data } = await axiosInstance.post(url, variables);
            return { data };
        }
        
        // For all other 'create' operations, use the default provider's method.
        return baseDataProvider.create({ resource, variables });
    },
};