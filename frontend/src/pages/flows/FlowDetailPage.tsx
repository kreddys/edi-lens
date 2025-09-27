import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { FlowDetail as FlowDetailComponent } from './FlowDetail';

/**
 * FlowDetailPage - Wrapper component for FlowDetail that works with React Router
 * Extracts ID from URL params and provides routing callbacks
 */
const FlowDetailPage: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();

    const handleBack = () => {
        navigate('/flows');
    };

    const handleFlowUpdate = () => {
        // Refresh the current page or handle update logic
        window.location.reload();
    };

    if (!id) {
        return <div>Flow ID not found</div>;
    }

    return (
        <FlowDetailComponent
            processGroupId={id}
            onBack={handleBack}
            onFlowUpdate={handleFlowUpdate}
        />
    );
};

export default FlowDetailPage;