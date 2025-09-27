// FILE: frontend/src/providers/data.ts

import simpleRestProvider from "@refinedev/simple-rest";
import { DataProvider, GetOneParams, CreateParams, DeleteOneParams, CreateResponse } from "@refinedev/core";
import { BaseRecord } from "@refinedev/core";
import axios from "axios";

const axiosInstance = axios.create({
    baseURL: import.meta.env.VITE_API_URL,
});

axiosInstance.interceptors.request.use(
    (config) => {
        console.log("API request:", config);
        return config;
    },
    (error) => {
        console.error("API request error:", error);
        return Promise.reject(error);
    }
);

axiosInstance.interceptors.response.use(
    (response) => {
        console.log("API response:", {
            status: response.status,
            statusText: response.statusText,
            data: response.data
        });
        return response;
    },
    (error) => {
        console.error("API response error:", error);
        return Promise.reject(error);
    }
);

// Initialize the provider
const baseDataProvider = simpleRestProvider(
    import.meta.env.VITE_API_URL,
    axiosInstance
);

// Simplified data provider for flows and schemas
export const dataProvider: DataProvider = {
    ...baseDataProvider,

    // Custom method for flow operations
    custom: async ({ url, method, payload, query }) => {
        const fullUrl = url.startsWith('http') ? url : `${import.meta.env.VITE_API_URL}${url}`;

        try {
            const config = {
                method: method || 'GET',
                url: fullUrl,
                data: payload,
                params: query,
            };

            const response = await axiosInstance(config);
            return { data: response.data };
        } catch (error) {
            console.error('Custom API call error:', error);
            throw error;
        }
    },

    getList: async <TData extends BaseRecord = BaseRecord>(params: any) => {
        console.log("getList called with params:", params);

        // For schemas, use the base provider
        if (params.resource === "schemas") {
            const result = await baseDataProvider.getList<TData>(params);
            return {
                data: Array.isArray(result.data) ? result.data : [] as TData[],
                total: result.total || 0
            };
        }

        // For flows, use V1 API
        if (params.resource === "flows") {
            try {
                const response = await flowAPI.listFlows();
                let data = response.flows || [];

                // Apply filters if provided
                if (params.filters) {
                    params.filters.forEach((filter: any) => {
                        if (filter.operator === 'contains') {
                            data = data.filter((item: any) => 
                                item[filter.field]?.toLowerCase()?.includes(filter.value.toLowerCase())
                            );
                        }
                    });
                }

                // Apply sorting if provided
                if (params.sorters && params.sorters.length > 0) {
                    const sorter = params.sorters[0];
                    data.sort((a: any, b: any) => {
                        const aValue = a[sorter.field];
                        const bValue = b[sorter.field];
                        if (sorter.order === 'desc') {
                            return bValue > aValue ? 1 : -1;
                        }
                        return aValue > bValue ? 1 : -1;
                    });
                }

                // Apply pagination if provided
                if (params.pagination) {
                    const { current = 1, pageSize = 10 } = params.pagination;
                    const start = (current - 1) * pageSize;
                    data = data.slice(start, start + pageSize);
                }

                return {
                    data: data as TData[],
                    total: response.flows?.length || 0
                };
            } catch (error) {
                console.error('Error fetching flows:', error);
                return { data: [] as TData[], total: 0 };
            }
        }

        // For templates, use V1 API
        if (params.resource === "templates") {
            try {
                const response = await flowAPI.listTemplates();
                let data = response.templates || [];

                // Apply same filtering/sorting/pagination logic as flows
                if (params.filters) {
                    params.filters.forEach((filter: any) => {
                        if (filter.operator === 'contains') {
                            data = data.filter((item: any) => 
                                item[filter.field]?.toLowerCase()?.includes(filter.value.toLowerCase())
                            );
                        }
                    });
                }

                if (params.sorters && params.sorters.length > 0) {
                    const sorter = params.sorters[0];
                    data.sort((a: any, b: any) => {
                        const aValue = a[sorter.field];
                        const bValue = b[sorter.field];
                        if (sorter.order === 'desc') {
                            return bValue > aValue ? 1 : -1;
                        }
                        return aValue > bValue ? 1 : -1;
                    });
                }

                if (params.pagination) {
                    const { current = 1, pageSize = 10 } = params.pagination;
                    const start = (current - 1) * pageSize;
                    data = data.slice(start, start + pageSize);
                }

                return {
                    data: data as TData[],
                    total: response.templates?.length || 0
                };
            } catch (error) {
                console.error('Error fetching templates:', error);
                return { data: [] as TData[], total: 0 };
            }
        }

        // Default behavior for other resources
        const result = await baseDataProvider.getList<TData>(params);
        return {
            data: Array.isArray(result.data) ? result.data : [] as TData[],
            total: result.total || 0
        };
    },

    getOne: async <TData extends BaseRecord = BaseRecord>(params: GetOneParams) => {
        console.log("getOne called with params:", params);

        // For flows, use V1 API
        if (params.resource === "flows") {
            try {
                const data = await flowAPI.getFlow(params.id.toString());
                return { data: data as TData };
            } catch (error) {
                console.error(`Error fetching flow ${params.id}:`, error);
                throw error;
            }
        }

        // For templates, use V1 API
        if (params.resource === "templates") {
            try {
                const data = await flowAPI.getTemplate(params.id.toString(), true); // include definition
                return { data: data as TData };
            } catch (error) {
                console.error(`Error fetching template ${params.id}:`, error);
                throw error;
            }
        }

        // Default behavior for other resources
        return await baseDataProvider.getOne<TData>(params);
    },

    create: async <TData extends BaseRecord = BaseRecord, TVariables = {}>({ resource, variables }: CreateParams<TVariables>) => {
        console.log("create called with params:", { resource, variables });

        // Handle flow creation with V1 API
        if (resource === "flows") {
            try {
                const data = await flowAPI.createFlow(variables);
                return { data } as CreateResponse<TData>;
            } catch (error) {
                console.error('Error creating flow:', error);
                throw error;
            }
        }

        // Handle schema copy operations
        const copyMatch = resource.match(/^schemas\/(.+)\/copy$/);
        if (copyMatch) {
            const baseSchemaName = copyMatch[1];
            const url = `/schemas/${baseSchemaName}/copy`;
            const { data } = await axiosInstance.post(url, variables);
            return { data } as CreateResponse<TData>;
        }

        return await baseDataProvider.create<TData, TVariables>({ resource, variables });
    },

    update: async ({ resource, id, variables }) => {
        console.log(`update called for ${resource}/${id}`, variables);

        // Handle flow updates with V1 API
        if (resource === "flows") {
            try {
                const data = await flowAPI.updateFlow(id.toString(), variables);
                return { data };
            } catch (error) {
                console.error(`Error updating flow ${id}:`, error);
                throw error;
            }
        }

        // Default behavior for other resources
        const { data } = await axiosInstance.put(`/${resource}/${id}`, variables);
        return { data };
    },

    deleteOne: async <TData extends BaseRecord = BaseRecord, TVariables = {}>(params: DeleteOneParams<TVariables>) => {
        console.log("deleteOne called with params:", params);

        // Handle flow deletion with V1 API
        if (params.resource === "flows") {
            try {
                await flowAPI.deleteFlow(params.id.toString());
                return { data: { id: params.id } as TData };
            } catch (error) {
                console.error(`Error deleting flow ${params.id}:`, error);
                throw error;
            }
        }

        // Default behavior for other resources
        return await baseDataProvider.deleteOne<TData, TVariables>(params);
    },
};

// Flow-specific API functions (V1 RESTful API)
export const flowAPI = {
    // Core Flow Management
    listFlows: async () => {
        const { data } = await axiosInstance.get('/api/v1/flows/');
        return data;
    },

    createFlow: async (flowDefinition: any) => {
        const { data } = await axiosInstance.post('/api/v1/flows/', flowDefinition);
        return data;
    },

    getFlow: async (flowId: string) => {
        const { data } = await axiosInstance.get(`/api/v1/flows/${flowId}`);
        return data;
    },

    updateFlow: async (flowId: string, updates: any) => {
        const { data } = await axiosInstance.put(`/api/v1/flows/${flowId}`, updates);
        return data;
    },

    deleteFlow: async (flowId: string) => {
        await axiosInstance.delete(`/api/v1/flows/${flowId}`);
        return { message: 'Flow deleted successfully' };
    },

    // Flow Execution
    startFlow: async (flowId: string) => {
        const { data } = await axiosInstance.post(`/api/v1/flows/${flowId}/executions/start`);
        return data;
    },

    stopFlow: async (flowId: string) => {
        const { data } = await axiosInstance.post(`/api/v1/flows/${flowId}/executions/stop`);
        return data;
    },

    getFlowStatus: async (flowId: string) => {
        const { data } = await axiosInstance.get(`/api/v1/flows/${flowId}/executions/status`);
        return data;
    },

    // Flow Deployments
    deployFlow: async (flowId: string, deploymentConfig: any = {}) => {
        const { data } = await axiosInstance.post(`/api/v1/flows/${flowId}/deployments`, deploymentConfig);
        return data;
    },

    getDeploymentStatus: async (flowId: string) => {
        const { data } = await axiosInstance.get(`/api/v1/flows/${flowId}/deployments`);
        return data;
    },

    undeployFlow: async (flowId: string) => {
        await axiosInstance.delete(`/api/v1/flows/${flowId}/deployments`);
        return { message: 'Flow undeployed successfully' };
    },

    // Flow Versions
    getFlowVersions: async (flowId: string) => {
        const { data } = await axiosInstance.get(`/api/v1/flows/${flowId}/versions`);
        return data;
    },

    createFlowVersion: async (flowId: string, versionData: any) => {
        const { data } = await axiosInstance.post(`/api/v1/flows/${flowId}/versions`, versionData);
        return data;
    },

    // Templates
    listTemplates: async () => {
        const { data } = await axiosInstance.get('/api/v1/templates/');
        return data;
    },

    getTemplate: async (templateId: string, includeDefinition = false) => {
        const { data } = await axiosInstance.get(`/api/v1/templates/${templateId}?include_definition=${includeDefinition}`);
        return data;
    },

    validateTemplate: async (templateId: string, parameters: any = {}) => {
        const { data } = await axiosInstance.post(`/api/v1/templates/${templateId}/validate`, {
            parameters,
            strict: true
        });
        return data;
    },

    // Registry Operations
    listBuckets: async () => {
        const { data } = await axiosInstance.get('/api/v1/registry/buckets/');
        return data;
    },

    createBucket: async (bucketData: { name: string; description?: string }) => {
        const { data } = await axiosInstance.post('/api/v1/registry/buckets/', bucketData);
        return data;
    },

    getBucket: async (bucketId: string) => {
        const { data } = await axiosInstance.get(`/api/v1/registry/buckets/${bucketId}`);
        return data;
    },

    deleteBucket: async (bucketId: string) => {
        try {
            await axiosInstance.delete(`/api/v1/registry/buckets/${bucketId}`);
            return { message: 'Bucket deleted successfully' };
        } catch (error: any) {
            // Handle 501 Not Implemented gracefully
            if (error.response?.status === 501) {
                return { message: 'Bucket deletion not yet implemented' };
            }
            throw error;
        }
    },

    listRegistryFlows: async () => {
        const { data } = await axiosInstance.get('/api/v1/registry/flows/');
        return data;
    },

    getRegistryFlow: async (flowId: string) => {
        const { data } = await axiosInstance.get(`/api/v1/registry/flows/${flowId}`);
        return data;
    },

    getRegistryFlowVersions: async (flowId: string) => {
        const { data } = await axiosInstance.get(`/api/v1/registry/flows/${flowId}/versions`);
        return data;
    },

    // Legacy compatibility methods (marked for deprecation)
    deployAndStore: async (flowDefinition: any, bucketId: string, parameters: any = {}) => {
        console.warn('deployAndStore is deprecated, use createFlow instead');
        return await flowAPI.createFlow({
            name: flowDefinition.name,
            description: flowDefinition.description || '',
            bucket_id: bucketId,
            definition: flowDefinition,
            parameters
        });
    },

    getStatus: async (flowId: string) => {
        console.warn('getStatus is deprecated, use getFlow instead');
        return await flowAPI.getFlow(flowId);
    },

    start: async (flowId: string) => {
        console.warn('start is deprecated, use startFlow instead');
        return await flowAPI.startFlow(flowId);
    },

    stop: async (flowId: string) => {
        console.warn('stop is deprecated, use stopFlow instead');
        return await flowAPI.stopFlow(flowId);
    },

    delete: async (flowId: string) => {
        console.warn('delete is deprecated, use deleteFlow instead');
        return await flowAPI.deleteFlow(flowId);
    },

    listDeployedFlows: async () => {
        console.warn('listDeployedFlows is deprecated, use listFlows instead');
        return await flowAPI.listFlows();
    },

    // Version control operations (not yet implemented in V1 API)
    commit: async (_flowId: string, _comments = 'Updated flow') => {
        throw new Error('Version control operations not yet implemented in V1 API');
    },

    updateFromRegistry: async (_flowId: string) => {
        throw new Error('Version control operations not yet implemented in V1 API');
    },

    revert: async (_flowId: string) => {
        throw new Error('Version control operations not yet implemented in V1 API');
    },

    getModifications: async (_flowId: string) => {
        throw new Error('Version control operations not yet implemented in V1 API');
    },

    listFlowsInBucket: async (_bucketId: string) => {
        throw new Error('Bucket-specific flow listing not yet implemented in V1 API');
    },

    getFlowFromRegistry: async (_bucketId: string, flowId: string, _version?: number) => {
        console.warn('getFlowFromRegistry is deprecated, use getRegistryFlow instead');
        return await flowAPI.getRegistryFlow(flowId);
    }
};

