import React, { useState } from "react";
import { Show } from "@refinedev/antd";
import { useShow } from "@refinedev/core";
import { Card, Descriptions, Button, Space, Tag, notification } from "antd";
import { PlayCircleOutlined, PauseCircleOutlined, EditOutlined, ReloadOutlined } from "@ant-design/icons";
import { flowAPI } from "../../providers/data";

export const FlowShow: React.FC = () => {
    const { queryResult } = useShow();
    const { data, isLoading, refetch } = queryResult;
    const [actionLoading, setActionLoading] = useState<string | null>(null);

    const record = data?.data;

    const handleStartFlow = async () => {
        if (!record?.id) return;
        
        setActionLoading('start');
        try {
            await flowAPI.startFlow(record.id.toString());
            notification.success({
                message: 'Success',
                description: 'Flow started successfully'
            });
            refetch();
        } catch (error) {
            console.error('Failed to start flow:', error);
            notification.error({
                message: 'Error', 
                description: 'Failed to start flow'
            });
        } finally {
            setActionLoading(null);
        }
    };

    const handleStopFlow = async () => {
        if (!record?.id) return;
        
        setActionLoading('stop');
        try {
            await flowAPI.stopFlow(record.id.toString());
            notification.success({
                message: 'Success',
                description: 'Flow stopped successfully'
            });
            refetch();
        } catch (error) {
            console.error('Failed to stop flow:', error);
            notification.error({
                message: 'Error',
                description: 'Failed to stop flow'
            });
        } finally {
            setActionLoading(null);
        }
    };

    const handleRefresh = () => {
        refetch();
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'running': return 'green';
            case 'stopped': return 'default';
            case 'invalid': return 'red';
            case 'unknown': return 'orange';
            default: return 'default';
        }
    };

    const getDeploymentStatusColor = (status: string) => {
        switch (status) {
            case 'deployed': return 'blue';
            case 'undeployed': return 'default';
            case 'failed': return 'red';
            default: return 'default';
        }
    };

    return (
        <Show isLoading={isLoading}>
            <Card 
                title="Flow Details"
                extra={
                    <Space>
                        <Button
                            icon={<ReloadOutlined />}
                            onClick={handleRefresh}
                            loading={isLoading}
                        >
                            Refresh
                        </Button>
                        {record?.status?.toLowerCase() === 'running' ? (
                            <Button 
                                icon={<PauseCircleOutlined />}
                                onClick={handleStopFlow}
                                loading={actionLoading === 'stop'}
                                disabled={actionLoading !== null}
                            >
                                Stop
                            </Button>
                        ) : (
                            <Button 
                                type="primary" 
                                icon={<PlayCircleOutlined />}
                                onClick={handleStartFlow}
                                loading={actionLoading === 'start'}
                                disabled={actionLoading !== null}
                            >
                                Start
                            </Button>
                        )}
                        <Button 
                            icon={<EditOutlined />}
                            href={`/flows/${record?.id}/edit`}
                        >
                            Edit
                        </Button>
                    </Space>
                }
            >
                <Descriptions column={2} bordered>
                    <Descriptions.Item label="Name">
                        {record?.name}
                    </Descriptions.Item>
                    <Descriptions.Item label="Description" span={2}>
                        {record?.description || 'No description provided'}
                    </Descriptions.Item>
                    <Descriptions.Item label="Execution Status">
                        <Tag color={getStatusColor(record?.status)}>
                            {record?.status === 'unknown' ? 'Not Started' : record?.status}
                        </Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="Deployment Status">
                        <Tag color={getDeploymentStatusColor(record?.deployment_status)}>
                            {record?.deployment_status}
                        </Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="Created">
                        {record?.created_at && record.created_at !== "Not available" ? 
                            new Date(record.created_at).toLocaleString() : 
                            <span style={{ color: '#999', fontStyle: 'italic' }}>Not available</span>
                        }
                    </Descriptions.Item>
                    <Descriptions.Item label="Last Updated">
                        {record?.updated_at && record.updated_at !== "Not available" ? 
                            new Date(record.updated_at).toLocaleString() : 
                            <span style={{ color: '#999', fontStyle: 'italic' }}>Not available</span>
                        }
                    </Descriptions.Item>
                </Descriptions>
            </Card>
        </Show>
    );
};