import React from "react";
import { useParams } from "react-router-dom";
import { useOne } from "@refinedev/core";
import { Spin, Result } from "antd";
import { TradingPartnerForm, TradingPartnerData } from "./TradingPartnerForm"; // <-- Import the new form

export const TradingPartnerEdit: React.FC = () => {
    const { id } = useParams();

    const { data, isLoading, isError } = useOne<TradingPartnerData>({
        resource: "trading-partners",
        id: id!,
    });

    if (isLoading) {
        return <div style={{ display: "flex", justifyContent: "center", padding: "50px" }}><Spin size="large" /></div>;
    }

    if (isError) {
        return <Result status="error" title="Could not load trading partner data." />;
    }

    return (
        <TradingPartnerForm
            mode="edit"
            initialData={data?.data}
        />
    );
};