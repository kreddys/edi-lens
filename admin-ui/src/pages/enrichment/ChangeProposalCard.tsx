// FILE: admin-ui/src/pages/enrichment/ChangeProposalCard.tsx
import React from 'react';
// We only need Typography from antd, no separate Code import.
import { Card, Tag, Typography, Button, Space } from 'antd';
import ReactDiffViewer from 'react-diff-viewer-continued';
import { useApiUrl, useCustomMutation } from '@refinedev/core';

// We only need Text.
const { Text } = Typography;

interface ChangeProposalCardProps {
    patch: {
        op: 'add' | 'replace' | 'remove';
        path: string;
        value?: any;
    };
}

const getTagColor = (op: string) => {
    if (op === 'add') return 'success';
    if (op === 'replace') return 'warning';
    if (op === 'remove') return 'error';
    return 'default';
};

export const ChangeProposalCard: React.FC<ChangeProposalCardProps> = ({ patch }) => {
    const apiUrl = useApiUrl();

    const { mutate: applyPatch, isLoading } = useCustomMutation<any>();

    const handleApply = () => {
        const schemaName = '837.5010.X222.A1.json'; 
        
        applyPatch({
            url: `${apiUrl}/enrichment/apply`,
            method: 'post',
            values: {
                schema_name: schemaName,
                patch: patch
            },
            meta: {
                successNotification: () => ({
                    message: 'Patch Applied',
                    description: `Successfully applied change to ${patch.path}.`,
                    type: 'success',
                }),
                errorNotification: (error: any) => ({
                    message: `Failed to Apply Patch`,
                    description: error?.message || 'An unknown error occurred.',
                    type: 'error',
                }),
            }
        });
    };

    return (
        <Card
            type="inner"
            title={
                <Space>
                    <Tag color={getTagColor(patch.op)}>{patch.op.toUpperCase()}</Tag>
                    <Text>Target:</Text>
                    {/* --- THIS IS THE FIX --- */}
                    {/* Use the 'code' prop on the Text component */}
                    <Text code>{patch.path}</Text>
                </Space>
            }
            extra={
                <Button type="primary" onClick={handleApply} loading={isLoading}>
                    Apply Change
                </Button>
            }
        >
            <ReactDiffViewer
                oldValue={patch.op === 'add' ? '' : '... (old value not available yet) ...'}
                newValue={JSON.stringify(patch.value, null, 2)}
                splitView={false}
                hideLineNumbers={true}
            />
        </Card>
    );
};