import simpleRestProvider from "@refinedev/simple-rest";
import { DataProvider } from "@refinedev/core";
import axios from "axios";
import keycloak from "./keycloak";
import getLogger from './logger';

const logger = getLogger('DATA');
const axiosInstance = axios.create();

axiosInstance.interceptors.request.use(
    (config) => {
        logger.debug(`Requesting: ${config.method?.toUpperCase()} ${config.url}`);
        const selectedTenant = localStorage.getItem('selected_tenant');

        if (keycloak.authenticated && keycloak.token) {
            config.headers.Authorization = `Bearer ${keycloak.token}`;
            logger.debug("Attached Authorization header.");
        }
        
        if (selectedTenant) {
            config.headers['X-Tenant-ID'] = selectedTenant;
            logger.debug(`Attached X-Tenant-ID header: ${selectedTenant}`);
        } else {
            logger.warn('No tenant selected. Halting API request.');
            return Promise.reject(new axios.Cancel('No tenant selected'));
        }

        return config;
    },
    (error) => {
        logger.error("Axios request error:", error);
        return Promise.reject(error);
    }
);

axiosInstance.interceptors.response.use(
    (response) => {
        logger.debug(`Response from ${response.config.url}:`, response.status, response.data);
        return response;
    },
    (error) => {
        logger.error("Axios response error:", error.response?.status, error.response?.data);
        return Promise.reject(error);
    }
)

export const dataProvider: DataProvider = simpleRestProvider(
    import.meta.env.VITE_API_URL, 
    axiosInstance
);