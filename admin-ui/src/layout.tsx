import { AppBar, Layout, LayoutProps, useGetIdentity, UserMenu } from 'react-admin';
import { MenuItem, Select, SelectChangeEvent, Typography } from '@mui/material';
import { useEffect, useState } from 'react';

// The Tenant Selector Component
const TenantSelector = () => {
    const { data: identity, isLoading } = useGetIdentity();
    const [selectedTenant, setSelectedTenant] = useState(
        localStorage.getItem('selected_tenant') || ''
    );

    useEffect(() => {
        // --- THIS IS THE FIX ---
        // Check if identity and identity.groups exist before accessing them
        if (!isLoading && identity && identity.groups && identity.groups.length > 0 && !selectedTenant) {
            const defaultTenant = identity.groups[0];
            localStorage.setItem('selected_tenant', defaultTenant);
            setSelectedTenant(defaultTenant);
            // Optionally, reload to apply the default tenant immediately
            window.location.reload();
        }
    }, [isLoading, identity, selectedTenant]);

    const handleChange = (event: SelectChangeEvent) => {
        const newTenant = event.target.value;
        localStorage.setItem('selected_tenant', newTenant);
        window.location.reload(); 
    };
    
    // --- THIS IS THE FIX ---
    // Render nothing if loading or if the user has no groups (tenants)
    if (isLoading || !identity || !identity.groups || identity.groups.length === 0) {
        return null;
    }

    return (
        <Select
            value={selectedTenant}
            onChange={handleChange}
            variant="standard"
            sx={{ color: 'white', ml: 2, '& .MuiSelect-icon': { color: 'white' }, '& .MuiInput-underline:before': { borderBottomColor: 'white' } }}
        >
            {identity.groups.map((group: string) => (
                <MenuItem key={group} value={group}>
                    {group}
                </MenuItem>
            ))}
        </Select>
    );
};

// Custom AppBar including the Tenant Selector
const CustomAppBar = () => (
    <AppBar>
        <Typography flex="1" variant="h6" id="react-admin-title"></Typography>
        <TenantSelector />
        <UserMenu />
    </AppBar>
);

export const CustomLayout = (props: LayoutProps) => <Layout {...props} appBar={CustomAppBar} />;