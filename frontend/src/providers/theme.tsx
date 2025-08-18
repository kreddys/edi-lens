import { ConfigProvider, App as AntdApp } from "antd";
import { RefineThemes } from "@refinedev/antd";
import React from "react";

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    return (
        <ConfigProvider
            // --- THIS IS THE FIX ---
            // To get the default light theme, we simply don't specify the `algorithm`.
            // We just pass the Refine theme object. This will give you the
            // original white background with blue accents.
            theme={RefineThemes.Blue}
        >
            <AntdApp>{children}</AntdApp>
        </ConfigProvider>
    );
};