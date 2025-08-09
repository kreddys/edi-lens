import React from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useOne } from "@refinedev/core";
import { IResourceComponentsProps } from "@refinedev/core";
import { TradingPartnerWizard, TradingPartnerData } from "./TradingPartnerWizard";
import { Spin } from "antd";

export const TradingPartnerEdit: React.FC<IResourceComponentsProps> = () => {
    const navigate = useNavigate();
    const { id } = useParams();

    const { data, isLoading } = useOne({
        resource: "trading-partners",
        id: id!,
    });

    const handleSuccess = () => {
        navigate("/trading-partners");
    };

    const handleCancel = () => {
        navigate("/trading-partners");
    };

    if (isLoading) {
        return (
            <div style={{ display: "flex", justifyContent: "center", padding: "50px" }}>
                <Spin size="large" />
            </div>
        );
    }

    return (
        <TradingPartnerWizard
            mode="edit"
            initialData={data?.data as TradingPartnerData}
            onSuccess={handleSuccess}
            onCancel={handleCancel}
        />
    );
};