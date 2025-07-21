// FILE: admin-ui/src/pages/enrichment/list.tsx
import React, { useState } from 'react'; // Import useState
import { Card, Tabs, Typography } from 'antd';
import type { TabsProps } from 'antd';
import { CoPilotAnalysisTab } from './CoPilotAnalysisTab';
import { KnowledgeSourcesTab } from './KnowledgeSourcesTab';

const { Title } = Typography;

// This type is now needed in the parent
type TAnalysisResult = {
    job_id: string;
    status: "running" | "complete" | "failed";
    result?: any;
    error?: string;
};

export const EnrichmentPage: React.FC = () => {
    // --- THIS IS THE FIX ---
    // Lift all analysis-related state to the parent component.
    const [jobId, setJobId] = useState<string | null>(null);
    const [isLoadingJob, setIsLoadingJob] = useState<boolean>(false);
    const [analysisResult, setAnalysisResult] = useState<TAnalysisResult | null>(null);
    // --- END OF FIX ---

    const items: TabsProps['items'] = [
        {
            key: '1',
            label: 'Co-Pilot Analysis',
            // Pass state and setters down as props
            children: (
                <CoPilotAnalysisTab
                    jobId={jobId}
                    setJobId={setJobId}
                    isLoadingJob={isLoadingJob}
                    setIsLoadingJob={setIsLoadingJob}
                    analysisResult={analysisResult}
                    setAnalysisResult={setAnalysisResult}
                />
            ),
        },
        {
            key: '2',
            label: 'Knowledge Sources',
            children: <KnowledgeSourcesTab />,
        },
        {
            key: '3',
            label: 'Manual Editor',
            children: <Typography.Paragraph>A manual schema patch editor is coming soon.</Typography.Paragraph>,
            disabled: true,
        }
    ];

    return (
        <Card>
            <Title level={4}>Schema Co-Pilot</Title>
            {/* The `destroyInactiveTabPane` prop is an alternative, but lifting state is cleaner */}
            <Tabs defaultActiveKey="1" items={items} />
        </Card>
    );
};