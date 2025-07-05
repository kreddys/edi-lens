import simpleRestProvider from "@refinedev/simple-rest";
import { DataProvider } from "@refinedev/core";
import axios from "axios";

// Create an axios instance
const axiosInstance = axios.create();

// Use an interceptor to add headers to every request
axiosInstance.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('keycloak_token');
        const selectedTenant = localStorage.getItem('selected_tenant');

        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        
        if (selectedTenant) {
            config.headers['X-Tenant-ID'] = selectedTenant;
        } else {
            console.warn('No tenant selected. Halting API request.');
            // Cancel the request if no tenant is selected
            return Promise.reject(new axios.Cancel('No tenant selected'));
        }

        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// --- THIS IS THE FIX ---
// The `dataProvider` was not being exported.
// We pass the API URL and our custom axios instance to the simpleRestProvider.
export const dataProvider: DataProvider = simpleRestProvider(
    import.meta.env.VITE_API_URL, 
    axiosInstance
);