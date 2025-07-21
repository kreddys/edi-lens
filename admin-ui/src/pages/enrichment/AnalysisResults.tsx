// FILE: admin-ui/src/pages/enrichment/AnalysisResults.tsx
import React from 'react';
import { Card, Typography, Alert, Empty, Space } from 'antd';
import { ChangeProposalCard } from './ChangeProposalCard';

const { Title, Paragraph } = Typography;

type TAnalysisResult = {
    job_id: string;
    status: "running" | "complete" | "failed";
    result?: any;
    error?: string;
};

interface AnalysisResultsProps {
    data: TAnalysisResult;
}

export const AnalysisResults: React.FC<AnalysisResultsProps> = ({ data }) => {
    if (data.status === 'failed') {
        return <Alert message="Analysis Failed" description={data.error || 'An unknown error occurred.'} type="error" showIcon />;
    }

    if (data.status === 'complete' && !data.result) {
        return <Alert message="Analysis Complete" description="The analysis job finished but returned no result." type="warning" showIcon />;
    }

    const { reasoning, patches } = data.result;

    return (
        <Card>
            <Title level={4}>Analysis Results</Title>
            <Card type="inner" title="Agent Reasoning">
                <Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                    {reasoning || 'No reasoning provided.'}
                </Paragraph>
            </Card>

            <Title level={5} style={{ marginTop: 24, marginBottom: 16 }}>Proposed Changes</Title>
            
            {patches && patches.length > 0 ? (
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                    {patches.map((patch: any, index: number) => (
                        <ChangeProposalCard key={index} patch={patch} />
                    ))}
                </Space>
            ) : (
                <Empty description="The agent did not propose any changes." />
            )}
        </Card>
    );
};