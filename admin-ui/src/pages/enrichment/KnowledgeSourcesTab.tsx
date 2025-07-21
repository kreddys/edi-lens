// FILE: admin-ui/src/pages/enrichment/KnowledgeSourcesTab.tsx
import React from 'react';
import { useTable, useDelete, useApiUrl, BaseRecord } from '@refinedev/core';
import { Table, Upload, Button, Space, Tag, notification, Typography } from 'antd';
import { InboxOutlined, DeleteOutlined } from '@ant-design/icons';
import { keycloak } from '../../utils';

const { Dragger } = Upload;
const { Text } = Typography;

export const KnowledgeSourcesTab: React.FC = () => {
    const apiUrl = useApiUrl();

    // --- THIS IS THE FIX (Step 1) ---
    // Remove `pagination` from the destructuring since it's turned off.
    const { tableQueryResult, sorters, filters } = useTable<any>({
        resource: 'knowledge/sources',
        pagination: { mode: 'off' },
    });

    // Manually construct the tableProps object without pagination.
    const tableProps = {
        dataSource: tableQueryResult?.data?.data,
        loading: tableQueryResult?.isLoading,
        sorters,
        filters,
    };
    // --- END OF FIX ---

    const { mutate: deleteMutate } = useDelete();

    const handleDelete = (id: string) => {
        deleteMutate({
            resource: 'knowledge/sources',
            id: id,
            successNotification: () => ({
                message: 'Deletion successful',
                description: `Document ${id} is being removed from the knowledge base.`,
                type: 'success',
            }),
            errorNotification: (error) => ({
                message: 'Deletion Failed',
                description: error?.message || 'Could not delete the document.',
                type: 'error'
            }),
        });
    };

    const draggerProps = {
        name: 'files',
        multiple: true,
        action: `${apiUrl}/knowledge/ingest-guides`,
        headers: {
            Authorization: `Bearer ${keycloak.token}`,
            'X-Tenant-ID': localStorage.getItem('selected_tenant') || '',
        },
        onChange(info: any) {
            const { status } = info.file;
            if (status === 'done') {
                notification.success({
                    message: `${info.file.name} uploaded successfully.`,
                    description: 'Ingestion process has started in the background.',
                });
                tableQueryResult.refetch();
            } else if (status === 'error') {
                notification.error({
                    message: `${info.file.name} upload failed.`,
                    description: info.file.response?.detail || 'An unknown error occurred.',
                });
            }
        },
    };

    return (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
            <Dragger {...draggerProps}>
                <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                <p className="ant-upload-text">Click or drag .txt files to this area to upload</p>
                <p className="ant-upload-hint">
                    Upload new implementation guides or knowledge documents. The AI Co-Pilot will learn from these sources.
                </p>
            </Dragger>

            <Table {...tableProps} rowKey="id">
                <Table.Column dataIndex="fileName" title="File Name" />
                <Table.Column 
                    dataIndex="status" 
                    title="Status"
                    render={(status: string) => <Tag color={status === 'processed' ? 'green' : 'blue'}>{status?.toUpperCase()}</Tag>}
                />
                <Table.Column 
                    dataIndex="createdAt" 
                    title="Ingested At"
                    render={(value) => value ? <Text>{new Date(value).toLocaleString()}</Text> : 'N/A'}
                />
                <Table.Column
                    title="Actions"
                    dataIndex="actions"
                    render={(_, record: BaseRecord) => (
                        <Button 
                            danger
                            icon={<DeleteOutlined />} 
                            onClick={() => handleDelete(record.id as string)}
                        />
                    )}
                />
            </Table>
        </Space>
    );
};