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

        // For flows, return empty list for now - will be implemented with backend integration
        if (params.resource === "flows") {
            return {
                data: [] as TData[],
                total: 0
            };
        }

        // Default behavior
        const result = await baseDataProvider.getList<TData>(params);
        return {
            data: Array.isArray(result.data) ? result.data : [] as TData[],
            total: result.total || 0
        };
    },

    getOne: async <TData extends BaseRecord = BaseRecord>(params: GetOneParams) => {
        console.log("getOne called with params:", params);
        return await baseDataProvider.getOne<TData>(params);
    },

    create: async <TData extends BaseRecord = BaseRecord, TVariables = {}>({ resource, variables }: CreateParams<TVariables>) => {
        console.log("create called with params:", { resource, variables });

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
        const { data } = await axiosInstance.put(`/${resource}/${id}`, variables);
        return { data };
    },

    deleteOne: async <TData extends BaseRecord = BaseRecord, TVariables = {}>(params: DeleteOneParams<TVariables>) => {
        console.log("deleteOne called with params:", params);
        return await baseDataProvider.deleteOne<TData, TVariables>(params);
    },
};

// Flow-specific API functions
export const flowAPI = {
    // Deploy and store a flow
    deployAndStore: async (flowDefinition: any, bucketId: string, parameters: any = {}) => {
        const { data } = await axiosInstance.post('/api/flows/deploy-and-store', {
            bucket_id: bucketId,
            flow_definition: flowDefinition,
            parameters,
            flow_description: flowDefinition.description || ''
        });
        return data;
    },

    // Get flow status
    getStatus: async (processGroupId: string) => {
        const { data } = await axiosInstance.get(`/api/flows/${processGroupId}/status`);
        return data;
    },

    // Start flow
    start: async (processGroupId: string) => {
        const { data } = await axiosInstance.post(`/api/flows/${processGroupId}/start`);
        return data;
    },

    // Stop flow
    stop: async (processGroupId: string) => {
        const { data } = await axiosInstance.post(`/api/flows/${processGroupId}/stop`);
        return data;
    },

    // Delete flow
    delete: async (processGroupId: string, removeFromRegistry = false) => {
        const { data } = await axiosInstance.delete(`/api/flows/${processGroupId}?remove_from_registry=${removeFromRegistry}`);
        return data;
    },

    // Version control operations
    commit: async (processGroupId: string, comments = 'Updated flow') => {
        const { data } = await axiosInstance.post(`/api/flows/${processGroupId}/version-control/commit?comments=${encodeURIComponent(comments)}`);
        return data;
    },

    updateFromRegistry: async (processGroupId: string) => {
        const { data } = await axiosInstance.post(`/api/flows/${processGroupId}/version-control/update`);
        return data;
    },

    revert: async (processGroupId: string) => {
        const { data } = await axiosInstance.post(`/api/flows/${processGroupId}/version-control/revert`);
        return data;
    },

    getModifications: async (processGroupId: string) => {
        const { data } = await axiosInstance.get(`/api/flows/${processGroupId}/version-control/modifications`);
        return data;
    },

    // Registry operations
    listBuckets: async () => {
        const { data } = await axiosInstance.get('/api/flows/registry/buckets');
        return data;
    },

    listFlowsInBucket: async (bucketId: string) => {
        const { data } = await axiosInstance.get(`/api/flows/registry/buckets/${bucketId}/flows`);
        return data;
    },

    getFlowFromRegistry: async (bucketId: string, flowId: string, version?: number) => {
        const versionParam = version ? `?version=${version}` : '';
        const { data } = await axiosInstance.get(`/api/flows/registry/buckets/${bucketId}/flows/${flowId}${versionParam}`);
        return data;
    }
};