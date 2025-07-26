// FILE: admin-ui/src/pages/enrichment/list.tsx
import React from 'react';
import { Card, Typography } from 'antd';
import { KnowledgeSourcesTab } from './KnowledgeSourcesTab';

const { Title } = Typography;

export const EnrichmentPage: React.FC = () => {
    return (
        <Card>
            <Title level={4}>Knowledge Base Management</Title>
            <Typography.Paragraph type="secondary">
                Upload and manage the implementation guides (.txt files) that the AI Schema Generator will use as its source of truth.
                The generation process itself is run via a backend script.
            </Typography.Paragraph>
            <KnowledgeSourcesTab />
        </Card>
    );
};