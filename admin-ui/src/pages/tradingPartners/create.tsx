import React from "react";
import { useNavigate } from "react-router-dom";
import { IResourceComponentsProps } from "@refinedev/core";
import { TradingPartnerWizard } from "./TradingPartnerWizard";

export const TradingPartnerCreate: React.FC<IResourceComponentsProps> = () => {
    const navigate = useNavigate();

    const handleSuccess = () => {
        navigate("/trading-partners");
    };

    const handleCancel = () => {
        navigate("/trading-partners");
    };

    return (
        <TradingPartnerWizard
            mode="create"
            onSuccess={handleSuccess}
            onCancel={handleCancel}
        />
    );
};