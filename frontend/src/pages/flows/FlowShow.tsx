import React from "react";
import { Show } from "@refinedev/antd";
import { useShow } from "@refinedev/core";
import { Card, Descriptions, Button, Space, Tag } from "antd";
import { PlayCircleOutlined, PauseCircleOutlined, EditOutlined } from "@ant-design/icons";

export const FlowShow: React.FC = () => {
    const { queryResult } = useShow();
    const { data, isLoading } = queryResult;

    const record = data?.data;

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
                            type="primary" 
                            icon={<PlayCircleOutlined />}
                            onClick={() => {
                                // Handle start flow
                                console.log('Start flow:', record?.id);
                            }}
                        >
                            Start
                        </Button>
                        <Button 
                            icon={<PauseCircleOutlined />}
                            onClick={() => {
                                // Handle stop flow  
                                console.log('Stop flow:', record?.id);
                            }}
                        >
                            Stop
                        </Button>
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