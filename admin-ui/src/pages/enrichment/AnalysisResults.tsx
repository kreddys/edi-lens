// FILE: admin-ui/src/pages/enrichment/AnalysisResults.tsx
import React, { useState, useEffect } from 'react';
import { Card, Typography, Alert, Empty, Space, Button, notification } from 'antd';
import { CheckOutlined, CloseOutlined } from '@ant-design/icons';
import { ChangeProposalCard } from './ChangeProposalCard';
import { useApiUrl, useCustomMutation } from '@refinedev/core';

const { Title, Paragraph } = Typography;

type TPatch = {
    op: 'add' | 'replace' | 'remove';
    path: string;
    value?: any;
};

type TProposal = {
    patch: TPatch;
    status: 'pending' | 'accepted' | 'rejected';
};

interface AnalysisResultsProps {
    data: any; // The full TAnalysisResult object
}

export const AnalysisResults: React.FC<AnalysisResultsProps> = ({ data }) => {
    const apiUrl = useApiUrl();
    const [proposals, setProposals] = useState<TProposal[]>([]);

    const { mutate: applyPatch, isLoading: isApplying } = useCustomMutation();

    useEffect(() => {
        if (data?.result?.patches) {
            setProposals(
                data.result.patches.map((patch: TPatch) => ({ patch, status: 'pending' }))
            );
        }
    }, [data]);

    const handleDecision = (index: number, newStatus: 'accepted' | 'rejected') => {
        setProposals(current => 
            current.map((p, i) => i === index ? { ...p, status: newStatus } : p)
        );
    };

    const handleUpdatePatch = (index: number, newPatch: TPatch) => {
        setProposals(current =>
            current.map((p, i) => i === index ? { ...p, patch: newPatch } : p)
        );
        notification.success({ message: 'Proposal Updated', description: 'Your changes have been saved locally. Click "Apply Accepted" to finalize.' });
    };

    const handleApplyAll = () => {
        const acceptedPatches = proposals
            .filter(p => p.status === 'accepted')
            .map(p => p.patch);

        if (acceptedPatches.length === 0) {
            notification.warning({ message: 'No changes to apply', description: 'Please accept one or more proposals first.' });
            return;
        }

        const schemaName = '837.5010.X222.A1.json'; // Hardcoded for now
        acceptedPatches.forEach(patch => {
            applyPatch({
                url: `${apiUrl}/enrichment/apply`,
                method: 'post',
                values: { schema_name: schemaName, patch: patch },
                // --- THIS IS THE FIX ---
                // Wrap the notification handlers in a meta object
                meta: {
                    successNotification: () => ({ 
                        message: 'Patch Applied', 
                        description: `Successfully applied change to ${patch.path}.`, 
                        type: 'success' 
                    }),
                    errorNotification: (error: any) => ({ 
                        message: 'Failed to Apply Patch', 
                        description: error?.message || 'An unknown error occurred.', 
                        type: 'error' 
                    }),
                }
                // --- END OF FIX ---
            });
        });
    };

    if (data.status === 'failed') {
        return <Alert message="Analysis Failed" description={data.error || 'An unknown error occurred.'} type="error" showIcon />;
    }

    const { reasoning, patches } = data.result;
    const acceptedCount = proposals.filter(p => p.status === 'accepted').length;

    return (
        <Card>
            <Title level={4}>Review Co-Pilot Proposals</Title>
            <Card type="inner" title="Agent Reasoning">
                <Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                    {reasoning || 'No reasoning provided.'}
                </Paragraph>
            </Card>

            <div style={{ marginTop: 24, marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Title level={5} style={{ margin: 0 }}>Proposed Changes ({patches?.length || 0})</Title>
                <Space>
                    <Button onClick={() => setProposals(proposals.map(p => ({...p, status: 'rejected'})))} icon={<CloseOutlined />}>Reject All</Button>
                    <Button type="primary" onClick={handleApplyAll} loading={isApplying} icon={<CheckOutlined />}>Apply {acceptedCount > 0 ? acceptedCount : ''} Accepted</Button>
                </Space>
            </div>
            
            {proposals && proposals.length > 0 ? (
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                    {proposals.map((proposal, index) => (
                        <ChangeProposalCard
                            key={index}
                            proposal={proposal}
                            onDecision={(status) => handleDecision(index, status)}
                            onUpdatePatch={(newPatch) => handleUpdatePatch(index, newPatch)}
                        />
                    ))}
                </Space>
            ) : (
                <Empty description="The agent did not propose any changes." />
            )}
        </Card>
    );
};