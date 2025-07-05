import simpleRestProvider from 'ra-data-simple-rest';
import { DataProvider, fetchUtils } from 'react-admin';
import { authProvider } from './authProvider';

const httpClient = async (url: string, options: fetchUtils.Options = {}) => {
    if (!options.headers) {
        options.headers = new Headers({ Accept: 'application/json' });
    }
    
    const token = await authProvider.getToken();
    const selectedTenant = localStorage.getItem('selected_tenant');

    if (token) {
        (options.headers as Headers).set('Authorization', `Bearer ${token}`);
    }
    
    if (selectedTenant) {
        (options.headers as Headers).set('X-Tenant-ID', selectedTenant);
    } else {
        console.warn('No tenant selected. Returning empty data.');
        return Promise.resolve({ 
            status: 200, 
            headers: new Headers(), 
            body: JSON.stringify({ data: [], total: 0 }), 
            json: { data: [], total: 0 } 
        });
    }
    
    return fetchUtils.fetchJson(url, options);
};

const baseDataProvider = simpleRestProvider(import.meta.env.VITE_API_URL, httpClient);

export const dataProvider: DataProvider = {
    ...baseDataProvider,

    // --- THIS IS THE FIX ---
    // Prefix unused parameters with an underscore to satisfy the linter.
    generateContent: (_params: any) => Promise.reject(new Error('AI not implemented.')),
    getCompletion: (_params: any) => Promise.reject(new Error('AI not implemented.')),
};