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

// Flow-specific API functions (V1 RESTful API)
export const flowAPI = {
    // Create and deploy a flow 
    deployAndStore: async (flowDefinition: any, bucketId: string, parameters: any = {}) => {
        // Create flow first
        const createResponse = await axiosInstance.post('/api/v1/flows/', {
            name: flowDefinition.name,
            description: flowDefinition.description || '',
            bucket_id: bucketId,
            definition: flowDefinition,
            parameters
        });
        
        if (!createResponse.data.success) {
            throw new Error(createResponse.data.message || 'Failed to create flow');
        }
        
        const flowId = createResponse.data.id;
        
        // Deploy the flow
        const deployResponse = await axiosInstance.post(`/api/v1/flows/${flowId}/deployments`, {
            parent_group_id: 'root'
        });
        
        return {
            success: true,
            flow_id: flowId,
            process_group_id: deployResponse.data.process_group_id,
            parameter_context_id: deployResponse.data.parameter_context_id,
            message: "Flow created and deployed successfully"
        };
    },

    // Get flow status
    getStatus: async (processGroupId: string) => {
        // For now, return basic status structure until V1 endpoint is implemented
        return {
            process_group_id: processGroupId,
            running: false,
            processor_count: 0,
            stopped_count: 0,
            running_count: 0,
            invalid_count: 0,
            disabled_count: 0
        };
    },

    // Start flow
    start: async (processGroupId: string) => {
        const { data } = await axiosInstance.post('/api/v1/flows/executions', {
            process_group_id: processGroupId,
            action: 'start'
        });
        return { message: 'Flow started successfully' };
    },

    // Stop flow
    stop: async (processGroupId: string) => {
        const { data } = await axiosInstance.post('/api/v1/flows/executions', {
            process_group_id: processGroupId,
            action: 'stop'
        });
        return { message: 'Flow stopped successfully' };
    },

    // Delete flow
    delete: async (processGroupId: string, removeFromRegistry = false) => {
        const { data } = await axiosInstance.delete(`/api/v1/flows/${processGroupId}?remove_from_registry=${removeFromRegistry}`);
        return { message: 'Flow deleted successfully' };
    },

    // Version control operations (placeholder for V1)
    commit: async (processGroupId: string, comments = 'Updated flow') => {
        throw new Error('Version control operations not yet implemented in V1 API');
    },

    updateFromRegistry: async (processGroupId: string) => {
        throw new Error('Version control operations not yet implemented in V1 API');
    },

    revert: async (processGroupId: string) => {
        throw new Error('Version control operations not yet implemented in V1 API');
    },

    getModifications: async (processGroupId: string) => {
        throw new Error('Version control operations not yet implemented in V1 API');
    },

    // Registry operations
    listBuckets: async () => {
        const { data } = await axiosInstance.get('/api/v1/registry/buckets/');
        return data || [];
    },

    listFlowsInBucket: async (bucketId: string) => {
        const { data } = await axiosInstance.get(`/api/v1/registry/flows/?bucket_id=${bucketId}`);
        return data.flows || [];
    },

    getFlowFromRegistry: async (bucketId: string, flowId: string, version?: number) => {
        const versionParam = version ? `&version=${version}` : '';
        const { data } = await axiosInstance.get(`/api/v1/registry/flows/${flowId}?bucket_id=${bucketId}${versionParam}`);
        return data;
    },

    getFlowVersions: async (bucketId: string, flowId: string) => {
        const { data } = await axiosInstance.get(`/api/v1/registry/flows/${flowId}/versions?bucket_id=${bucketId}`);
        return data.versions || [];
    },

    createBucket: async (bucketName: string, description?: string) => {
        const { data } = await axiosInstance.post('/api/v1/registry/buckets/', {
            name: bucketName,
            description: description || ''
        });
        return data;
    },

    // List deployed flows in NiFi
    listDeployedFlows: async () => {
        const { data } = await axiosInstance.get('/api/v1/flows/?deployed_only=true');
        return data.flows || [];
    },

    // Templates
    listTemplates: async () => {
        const { data } = await axiosInstance.get('/api/v1/templates/');
        return data;
    },

    getTemplate: async (templateId: string) => {
        const { data } = await axiosInstance.get(`/api/v1/templates/${templateId}`);
        return data;
    }
};

