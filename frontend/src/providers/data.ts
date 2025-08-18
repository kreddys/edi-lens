// FILE: frontend/src/providers/data.ts

import simpleRestProvider from "@refinedev/simple-rest";
import { DataProvider, GetOneParams, CreateParams, DeleteOneParams, CreateResponse } from "@refinedev/core";
import { BaseRecord } from "@refinedev/core";
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
        logger.log("Axios response:", {
            status: response.status,
            statusText: response.statusText,
            headers: response.headers,
            data: response.data
        });
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
            // For workflows resource, add tenant_id as a query parameter
            if (params.resource === "workflows") {
                const selectedTenant = localStorage.getItem('selected_tenant');
                if (selectedTenant) {
                    // Build URL with tenant_id and pagination parameters
                    let url = `${import.meta.env.VITE_API_URL}/${params.resource}?tenant_id=${selectedTenant}`;
                    
                    // Add pagination parameters if they exist
                    if (params.pagination) {
                        const current = params.pagination.current || 1;
                        const pageSize = params.pagination.pageSize || 10;
                        const start = (current - 1) * pageSize;
                        const end = start + pageSize;
                        url += `&_start=${start}&_end=${end}`;
                    }
                    
                    // Add sorting parameters if they exist
                    if (params.sorters && params.sorters.length > 0) {
                        const sortParam = params.sorters.map(sort => 
                            `${sort.order === "desc" ? "-" : ""}${sort.field}`
                        ).join(",");
                        url += `&_sort=${sortParam}`;
                    }
                    
                    // Add filter parameters if they exist
                    if (params.filters && params.filters.length > 0) {
                        params.filters.forEach(filter => {
                            // Handle different filter types
                            if (filter.operator !== "or" && filter.operator !== "and" && 'field' in filter) {
                                // Skip tenant_id filter since we already added it
                                if (filter.field !== "tenant_id") {
                                    url += `&${filter.field}=${filter.value}`;
                                }
                            }
                        });
                    }
                    
                    // Make a direct axios call with the constructed URL
                    const response = await axiosInstance.get(url);
                    
                    // Transform the response to match what Refine expects
                    if (response.data && typeof response.data === 'object' && 'workflows' in response.data) {
                        logger.log("Transforming workflows data structure");
                        return {
                            data: response.data.workflows,
                            total: response.data.total
                        };
                    } else if (Array.isArray(response.data)) {
                        logger.log("Workflows data is already in correct array format");
                        return {
                            data: response.data,
                            total: response.data.length
                        };
                    } else {
                        logger.warn("Unexpected data structure for workflows:", response.data);
                        return {
                            data: [],
                            total: 0
                        };
                    }
                } else {
                    logger.warn("No tenant selected. Cannot fetch workflows.");
                    throw new Error("No tenant selected");
                }
            }
            
            const result = await baseDataProvider.getList(params);
            logger.log("getList raw result:", {
                data: result.data,
                total: result.total
            });
            
            // Transform the data if it's the workflow-templates resource
            if (params.resource === "workflow-templates" && result.data) {
                // For workflow-templates, the backend returns { templates: [], total: 0, page: 1, page_size: 20 }
                // But we need to check what structure we actually receive after the base provider processes it
                logger.log("Workflow templates raw data:", result.data);
                
                // Check if this is the raw backend response structure
                if (result.data && typeof result.data === 'object' && 'templates' in result.data && 'total' in result.data) {
                    logger.log("Transforming workflow-templates data structure from backend format");
                    // Transform the data to match what Refine expects
                    return {
                        data: result.data.templates,
                        total: result.data.total
                    };
                } 
                // If it's already been transformed by the base provider, it might be in the correct format
                else if (Array.isArray(result.data)) {
                    logger.log("Workflow templates data is already in correct array format");
                    return {
                        data: result.data,
                        total: result.data.length
                    };
                } 
                // Otherwise, log what we received
                else {
                    logger.warn("Unexpected data structure for workflow-templates:", result.data);
                    return {
                        data: [],
                        total: 0
                    };
                }
            }
            
            // Also handle the workflows resource which might have similar issues
            if (params.resource === "workflows" && result.data) {
                // Check if the data has the expected structure from our backend
                if (result.data && typeof result.data === 'object' && 'workflows' in result.data && 'total' in result.data) {
                    logger.log("Transforming workflows data structure");
                    // Transform the data to match what Refine expects
                    return {
                        data: result.data.workflows,
                        total: result.data.total
                    };
                } 
                // If it's already been transformed by the base provider, it might be in the correct format
                else if (Array.isArray(result.data)) {
                    logger.log("Workflows data is already in correct array format");
                    return {
                        data: result.data,
                        total: result.data.length
                    };
                } 
                // Otherwise, log what we received
                else {
                    logger.warn("Unexpected data structure for workflows:", result.data);
                    return {
                        data: [],
                        total: 0
                    };
                }
            }
            
            return {
                data: Array.isArray(result.data) ? result.data : [],
                total: result.total || 0
            };
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

    getOne: async <TData extends BaseRecord = BaseRecord>(params: GetOneParams) => {
        logger.log("getOne called with params:", params);
        try {
            const result = await baseDataProvider.getOne<TData>(params);
            logger.log("getOne result:", result);
            return result;
        } catch (error) {
            logger.error("Error in getOne:", error);
            throw error;
        }
    },

    create: async <TData extends BaseRecord = BaseRecord, TVariables = {}>({ resource, variables }: CreateParams<TVariables>) => {
        logger.log("create called with params:", { resource, variables });
        try {
            const copyMatch = resource.match(/^schemas\/(.+)\/copy$/);
            
            if (copyMatch) {
                const baseSchemaName = copyMatch[1];
                const url = `${import.meta.env.VITE_API_URL}/schemas/${baseSchemaName}/copy`;
                const { data } = await axiosInstance.post(url, variables);
                logger.log("create result:", data);
                return { data } as CreateResponse<TData>;
            }
            
            // For all other 'create' operations, use the default provider's method
            const result = await baseDataProvider.create<TData, TVariables>({ resource, variables });
            logger.log("create result:", result);
            return result;
        } catch (error) {
            logger.error("Error in create:", error);
            throw error;
        }
    },
    
    deleteOne: async <TData extends BaseRecord = BaseRecord, TVariables = {}>(params: DeleteOneParams<TVariables>) => {
        logger.log("deleteOne called with params:", params);
        try {
            const result = await baseDataProvider.deleteOne<TData, TVariables>(params);
            logger.log("deleteOne result:", result);
            return result;
        } catch (error) {
            logger.error("Error in deleteOne:", error);
            throw error;
        }
    },
};