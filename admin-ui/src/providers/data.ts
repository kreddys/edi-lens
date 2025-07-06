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
            logger.warn('No tenant selected. Halting API request.');
            return Promise.reject(new axios.Cancel('No tenant selected'));
        }
        return config;
    },
    (error) => Promise.reject(error)
);

export const dataProvider: DataProvider = simpleRestProvider(
    import.meta.env.VITE_API_URL, 
    axiosInstance
);