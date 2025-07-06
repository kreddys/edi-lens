import { ThemedLayoutV2, ThemedTitleV2 } from "@refinedev/antd";
import { useGetIdentity } from "@refinedev/core";
import { Layout as AntdLayout, Select, Typography, Avatar, Space, theme } from "antd";
import React, { useEffect, useState } from "react";

const { Header: AntdHeader } = AntdLayout;
const { useToken } = theme;

const TenantSelector = () => {
    const { data: identity } = useGetIdentity<{groups: string[]}>();
    const [selectedTenant, setSelectedTenant] = useState(localStorage.getItem('selected_tenant') || '');

    useEffect(() => {
        if (identity?.groups && identity.groups.length > 0 && !selectedTenant) {
            const defaultTenant = identity.groups[0];
            localStorage.setItem('selected_tenant', defaultTenant);
            setSelectedTenant(defaultTenant);
            window.location.reload();
        }
    }, [identity, selectedTenant]);

    const handleChange = (value: string) => {
        localStorage.setItem('selected_tenant', value);
        window.location.reload();
    };

    if (!identity?.groups || identity.groups.length === 0) return null;

    return (
        <Select
            value={selectedTenant}
            onChange={handleChange}
            options={identity.groups.map(group => ({ label: group, value: group }))}
            bordered={false}
            style={{ minWidth: 120 }}
        />
    );
};

const UserMenu = () => {
    const { data: identity } = useGetIdentity<{name: string, avatar: string}>();
    if (!identity) return null;

    return (
        <Space style={{ marginLeft: "16px" }}>
            <Avatar src={identity.avatar} />
            <Typography.Text strong>{identity.name}</Typography.Text>
        </Space>
    )
}

const CustomHeader: React.FC = () => {
    const { token } = useToken();
    return (
        <AntdHeader
            style={{
                backgroundColor: token.colorBgContainer,
                display: "flex",
                // --- THIS IS THE FIX ---
                // The header only contains right-aligned elements now.
                justifyContent: "flex-end",
                alignItems: "center",
                padding: "0 24px",
                height: "64px",
                position: "sticky",
                top: 0,
                zIndex: 1,
            }}
        >
            <Space>
                <TenantSelector />
                <UserMenu />
            </Space>
        </AntdHeader>
    );
};


export const Layout = ({ children }: { children: React.ReactNode }) => {
    return (
        <ThemedLayoutV2
            Header={CustomHeader}
            // --- THIS IS THE FIX ---
            // We re-introduce the `Title` prop to `ThemedLayoutV2`.
            // This prop specifically targets the title area in the Sider (sidebar).
            Title={({ collapsed }) => (
                <ThemedTitleV2
                    collapsed={collapsed}
                    text="EDI Lens" // Your project name here
                />
            )}
        >
            {children}
        </ThemedLayoutV2>
    );
};