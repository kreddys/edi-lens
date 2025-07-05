import { ThemedLayoutV2, ThemedTitleV2 } from "@refinedev/mui";
import { useGetIdentity } from "@refinedev/core";
import { AppBar, MenuItem, Select, SelectChangeEvent, Toolbar, Typography, Avatar } from "@mui/material";
import { useEffect, useState } from "react";

const TenantSelector = () => {
    // We expect the identity to have a 'groups' property
    const { data: identity } = useGetIdentity<{groups: string[], name: string}>();
    const [selectedTenant, setSelectedTenant] = useState(localStorage.getItem('selected_tenant') || '');

    useEffect(() => {
        if (identity?.groups && identity.groups.length > 0 && !selectedTenant) {
            const defaultTenant = identity.groups[0];
            localStorage.setItem('selected_tenant', defaultTenant);
            setSelectedTenant(defaultTenant);
            window.location.reload();
        }
    }, [identity, selectedTenant]);

    const handleChange = (event: SelectChangeEvent) => {
        localStorage.setItem('selected_tenant', event.target.value);
        window.location.reload();
    };

    if (!identity?.groups || identity.groups.length === 0) return null;

    return (
        <Select
            value={selectedTenant}
            onChange={handleChange}
            variant="standard"
            sx={{ color: 'white', ml: 2, '& .MuiSelect-icon': { color: 'white' }, '& .MuiInput-underline:before': { borderBottomColor: 'white' } }}
        >
            {identity.groups.map((group: string) => (
                <MenuItem key={group} value={group}>{group}</MenuItem>
            ))}
        </Select>
    );
};

// A simple user menu component to show avatar and name
const UserMenu = () => {
    const { data: identity } = useGetIdentity<{name: string}>();
    if (!identity) return null;

    return (
        <div style={{display: 'flex', alignItems: 'center', marginLeft: '16px'}}>
            <Avatar sx={{ width: 32, height: 32, marginRight: '8px' }} />
            <Typography color="white">{identity.name}</Typography>
        </div>
    )
}

const Header = () => (
    <AppBar position="sticky">
        <Toolbar>
            <ThemedTitleV2 collapsed={false} />
            <Typography sx={{ flex: 1 }}></Typography>
            <TenantSelector />
            <UserMenu />
        </Toolbar>
    </AppBar>
);

export const Layout = ({ children }: { children: React.ReactNode }) => (
    <ThemedLayoutV2 Header={Header}>
        {children}
    </ThemedLayoutV2>
);