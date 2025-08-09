import React from "react";
import { useNavigate } from "react-router-dom";
import { TradingPartnerForm } from "./TradingPartnerForm"; // <-- Import the new form

export const TradingPartnerCreate: React.FC = () => {
    const navigate = useNavigate();

    return (
        <TradingPartnerForm
            mode="create"
            onSuccess={() => {
                navigate("/trading-partners");
            }}
        />
    );
};