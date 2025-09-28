import React, { useState } from "react";
import { Show } from "@refinedev/antd";
import { useShow } from "@refinedev/core";
import { Card, Descriptions, Button, Space, Tag, notification, Table } from "antd";
import { PlayCircleOutlined, PauseCircleOutlined, EditOutlined, ReloadOutlined, SettingOutlined } from "@ant-design/icons";
import { flowAPI } from "../../providers/data";
import { ParameterEditModal } from "../../components/ParameterEditModal";

export const FlowShow: React.FC = () => {
    const { queryResult } = useShow();
    const { data, isLoading, refetch } = queryResult;
    const [actionLoading, setActionLoading] = useState<string | null>(null);
    const [parameterModalOpen, setParameterModalOpen] = useState(false);

    const record = data?.data;

    const handleToggleFlow = async () => {
        if (!record?.id) return;
        
        // Check if flow has processors
        if (record?.processor_count === 0) {
            notification.warning({
                message: 'Cannot Start Empty Flow',
                description: 'This flow has no processors to start. Please add processors first.'
            });
            return;
        }
        
        const isRunning = record?.status?.toLowerCase() === 'running';
        const action = isRunning ? 'stop' : 'start';
        
        setActionLoading(action);
        try {
            if (isRunning) {
                await flowAPI.stopFlow(record.id.toString());
                notification.success({
                    message: 'Success',
                    description: 'Flow stopped successfully'
                });
            } else {
                await flowAPI.startFlow(record.id.toString());
                notification.success({
                    message: 'Success',
                    description: 'Flow started successfully'
                });
            }
            
            // Refetch after a short delay to allow NiFi to update
            setTimeout(async () => {
                await refetch();
            }, 2000);
            
        } catch (error) {
            console.error(`Failed to ${action} flow:`, error);
            notification.error({
                message: 'Error',
                description: `Failed to ${action} flow`
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
                        <Button 
                            type={record?.status?.toLowerCase() === 'running' ? 'default' : 'primary'}
                            icon={record?.status?.toLowerCase() === 'running' ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                            onClick={handleToggleFlow}
                            loading={actionLoading !== null}
                            disabled={actionLoading !== null || (record?.processor_count === 0)}
                        >
                            {record?.status?.toLowerCase() === 'running' ? 'Stop' : 'Start'}
                            {record?.processor_count === 0 && ' (No Processors)'}
                        </Button>
                        <Button 
                            icon={<EditOutlined />}
                            href={`/flows/${record?.id}/edit`}
                        >
                            Edit
                        </Button>
                        <Button 
                            icon={<SettingOutlined />}
                            onClick={() => setParameterModalOpen(true)}
                            disabled={!record?.id}
                        >
                            Parameters
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
                
                {/* Parameters Section */}
                {record?.parameters && Object.keys(record.parameters).length > 0 && (
                    <Card 
                        title="Flow Parameters" 
                        style={{ marginTop: 16 }}
                        size="small"
                    >
                        <Table
                            size="small"
                            pagination={false}
                            dataSource={Object.entries(record.parameters).map(([paramName, paramInfo], index) => {
                                // Handle both simple string values and object values with metadata
                                let paramValue: string;
                                let paramDescription: string;
                                let isSensitive = false;

                                if (typeof paramInfo === 'object' && paramInfo !== null) {
                                    // Standard parameter object with value, description, sensitive
                                    const paramObj = paramInfo as any;
                                    paramValue = paramObj.value;
                                    paramDescription = paramObj.description || '';
                                    isSensitive = paramObj.sensitive || false;

                                    // Handle case where value contains stringified parameter object (Python dict format)
                                    if (typeof paramValue === 'string' && paramValue.startsWith('{') && (paramValue.includes("'value'") || paramValue.includes("'description'"))) {
                                        try {
                                            // Handle Python dict format with single quotes and Python booleans
                                            let processedString = paramValue
                                                .replace(/'/g, '"')           // Convert single quotes to double quotes
                                                .replace(/True/g, 'true')     // Convert Python True to JSON true
                                                .replace(/False/g, 'false')   // Convert Python False to JSON false
                                                .replace(/None/g, 'null');    // Convert Python None to JSON null
                                            
                                            const parsedParam = JSON.parse(processedString);
                                            paramValue = parsedParam.value || paramValue;
                                            paramDescription = parsedParam.description || paramDescription;
                                            isSensitive = parsedParam.sensitive || isSensitive;
                                        } catch (e) {
                                            // If parsing fails, display the value as-is but log the issue
                                            console.warn('Failed to parse parameter value as Python dict:', paramValue, e);
                                            // Don't change paramValue - display the raw string
                                        }
                                    }
                                } else if (typeof paramInfo === 'string' && paramInfo.startsWith('{') && (paramInfo.includes("'value'") || paramInfo.includes("'description'"))) {
                                    // Handle direct string that looks like a Python dict
                                    try {
                                        let processedString = paramInfo
                                            .replace(/'/g, '"')           // Convert single quotes to double quotes
                                            .replace(/True/g, 'true')     // Convert Python True to JSON true
                                            .replace(/False/g, 'false')   // Convert Python False to JSON false
                                            .replace(/None/g, 'null');    // Convert Python None to JSON null
                                        
                                        const parsedParam = JSON.parse(processedString);
                                        paramValue = parsedParam.value || '';
                                        paramDescription = parsedParam.description || '';
                                        isSensitive = parsedParam.sensitive || false;
                                    } catch (e) {
                                        // If parsing fails, treat as simple string value
                                        console.warn('Failed to parse parameter string as Python dict:', paramInfo, e);
                                        paramValue = String(paramInfo);
                                        paramDescription = '';
                                    }
                                } else {
                                    // Simple string value
                                    paramValue = String(paramInfo);
                                    paramDescription = '';
                                }
                                
                                return {
                                    key: index,
                                    parameterName: paramName,
                                    description: paramDescription,
                                    value: paramValue,
                                    sensitive: isSensitive
                                };
                            })}
                            columns={[
                                {
                                    title: 'Parameter Name',
                                    dataIndex: 'parameterName',
                                    key: 'parameterName',
                                    width: '25%',
                                    render: (text: string, record: any) => (
                                        <div>
                                            <span style={{ fontWeight: 500, fontFamily: 'monospace' }}>{text}</span>
                                            {record.sensitive && (
                                                <Tag color="orange" style={{ marginLeft: 8, fontSize: '11px' }}>
                                                    SENSITIVE
                                                </Tag>
                                            )}
                                        </div>
                                    ),
                                },
                                {
                                    title: 'Description',
                                    dataIndex: 'description',
                                    key: 'description',
                                    width: '35%',
                                    render: (text: string) => (
                                        <span style={{ color: text ? 'inherit' : '#999', fontStyle: text ? 'normal' : 'italic' }}>
                                            {text || 'No description'}
                                        </span>
                                    ),
                                },
                                {
                                    title: 'Value',
                                    dataIndex: 'value',
                                    key: 'value',
                                    width: '40%',
                                    render: (text: string) => (
                                        <span style={{ 
                                            fontFamily: 'monospace', 
                                            fontSize: '13px',
                                            color: text ? 'inherit' : '#999',
                                            fontStyle: text ? 'normal' : 'italic'
                                        }}>
                                            {text || 'Empty'}
                                        </span>
                                    ),
                                },
                            ]}
                        />
                    </Card>
                )}
            </Card>

            <ParameterEditModal
                open={parameterModalOpen}
                onClose={() => setParameterModalOpen(false)}
                flowId={record?.id?.toString() || ''}
                flowName={record?.name || 'Unknown Flow'}
                initialParameters={record?.parameters || {}}
                onSuccess={() => {
                    refetch();
                    setParameterModalOpen(false);
                }}
            />
        </Show>
    );
};