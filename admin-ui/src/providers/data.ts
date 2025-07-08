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
            // For schemas, tenant is not required, so we don't halt the request.
            if (config.url && !config.url.includes("/schemas")) {
                logger.warn('No tenant selected. Halting API request.');
                return Promise.reject(new axios.Cancel('No tenant selected'));
            }
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Create a base provider with all the default behaviors (getList, getOne, create, etc.)
const baseDataProvider = simpleRestProvider(
    import.meta.env.VITE_API_URL, 
    axiosInstance
);

// --- THIS IS THE FIX ---
// Create our final dataProvider by wrapping the base one.
export const dataProvider: DataProvider = {
    ...baseDataProvider, // Inherit all default methods

    // Override the `update` method
    update: async ({ resource, id, variables }) => {
        // If we are updating the 'schemas' resource, use PUT.
        if (resource === "schemas") {
            const url = `${import.meta.env.VITE_API_URL}/${resource}/${id}`;
            const { data } = await axiosInstance.put(url, variables);
            return { data };
        }
        // For all other resources, use the default behavior from the base provider (which uses PATCH).
        return baseDataProvider.update({ resource, id, variables });
    },
};