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
        logger.log("Axios request:", config);
        return config;
    },
    (error) => {
        logger.error("Axios request error:", error);
        return Promise.reject(error);
    }
);

axiosInstance.interceptors.response.use(
    (response) => {
        logger.log("Axios response:", response);
        return response;
    },
    (error) => {
        logger.error("Axios response error:", error);
        return Promise.reject(error);
    }
);

// --- THIS IS THE FIX (Part 1) ---
// Initialize the provider with only the required 2 arguments.
const baseDataProvider = simpleRestProvider(
    import.meta.env.VITE_API_URL, 
    axiosInstance
);
// --- END OF FIX ---

// Custom data provider with debug logging and data transformation
export const dataProvider: DataProvider = {
    ...baseDataProvider,

    getList: async (params) => {
        logger.log("getList called with params:", params);
        try {
            const result = await baseDataProvider.getList(params);
            logger.log("getList result:", result);
            
            // Transform the data if it's the workflow-templates resource
            if (params.resource === "workflow-templates" && result.data) {
                // Check if the data has the expected structure from our backend
                if (result.data && typeof result.data === 'object' && 'templates' in result.data) {
                    logger.log("Transforming workflow-templates data structure");
                    // Transform the data to match what Refine expects
                    return {
                        data: result.data.templates,
                        total: result.data.total
                    };
                } else {
                    logger.warn("Unexpected data structure for workflow-templates:", result.data);
                }
            }
            
            return result;
        } catch (error) {
            logger.error("Error in getList:", error);
            throw error;
        }
    },

    // --- THIS IS THE FIX (Part 2) ---
    // Override the `update` method to use `axiosInstance.put` directly.
    // This is the correct way to force a PUT request for all update operations.
    update: async ({ resource, id, variables }) => {
        const url = `${import.meta.env.VITE_API_URL}/${resource}/${id}`;
        logger.log(`update called for ${resource}/${id}`, variables);
        try {
            const { data } = await axiosInstance.put(url, variables);
            logger.log("update result:", data);
            return { data };
        } catch (error) {
            logger.error("Error in update:", error);
            throw error;
        }
    },
    // --- END OF FIX ---

    // The special 'create' logic for copying schemas remains the same.
    getOne: async (params) => {
        logger.log("getOne called with params:", params);
        try {
            const result = await baseDataProvider.getOne(params);
            logger.log("getOne result:", result);
            return result;
        } catch (error) {
            logger.error("Error in getOne:", error);
            throw error;
        }
    },

    create: async ({ resource, variables }) => {
        logger.log("create called with params:", { resource, variables });
        try {
            const copyMatch = resource.match(/^schemas\/(.+)\/copy$/);
            
            if (copyMatch) {
                const baseSchemaName = copyMatch[1];
                const url = `${import.meta.env.VITE_API_URL}/schemas/${baseSchemaName}/copy`;
                const { data } = await axiosInstance.post(url, variables);
                logger.log("create result:", data);
                return { data };
            }
            
            // For all other 'create' operations, use the default provider's method.
            const result = await baseDataProvider.create({ resource, variables });
            logger.log("create result:", result);
            return result;
        } catch (error) {
            logger.error("Error in create:", error);
            throw error;
        }
    },
    
    deleteOne: async (params) => {
        logger.log("deleteOne called with params:", params);
        try {
            const result = await baseDataProvider.deleteOne(params);
            logger.log("deleteOne result:", result);
            return result;
        } catch (error) {
            logger.error("Error in deleteOne:", error);
            throw error;
        }
    },
};