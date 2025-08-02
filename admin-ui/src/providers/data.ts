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
                logger.warn('No tenant selected. Halting API request.');
                return Promise.reject(new axios.Cancel('No tenant selected'));
            }
        }
        return config;
    },
    (error) => Promise.reject(error)
);

const baseDataProvider = simpleRestProvider(
    import.meta.env.VITE_API_URL, 
    axiosInstance
);

export const dataProvider: DataProvider = {
    ...baseDataProvider,

    create: async ({ resource, variables }) => {
        const copyMatch = resource.match(/^schemas\/(.+)\/copy$/);
        
        if (copyMatch) {
            const baseSchemaName = copyMatch[1];
            const url = `${import.meta.env.VITE_API_URL}/schemas/${baseSchemaName}/copy`;
            const { data } = await axiosInstance.post(url, variables);
            return { data };
        }
        
        return baseDataProvider.create({ resource, variables });
    },

    update: async ({ resource, id, variables }) => {
        if (resource === "schemas") {
            const url = `${import.meta.env.VITE_API_URL}/${resource}/${id}`;
            const { data } = await axiosInstance.put(url, variables);
            return { data };
        }
        return baseDataProvider.update({ resource, id, variables });
    },
};