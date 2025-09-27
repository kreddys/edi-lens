import React from 'react';
import { Alert, Collapse, Typography, Tag, Space, Divider } from 'antd';
import { ExclamationCircleOutlined, BugOutlined, ToolOutlined } from '@ant-design/icons';

const { Panel } = Collapse;
const { Text, Paragraph } = Typography;

interface ErrorFailure {
  component_type: string;
  component_name: string;
  error_type: string;
  message: string;
  details: Record<string, any>;
}

interface ErrorDetailsProps {
  error: any;
  title?: string;
}

export const ErrorDetails: React.FC<ErrorDetailsProps> = ({ error, title = 'Error Details' }) => {
  // Extract error information from the response
  const errorData = error?.response?.data?.detail || error?.response?.data || {};
  const errorType = errorData.error_type || 'UNKNOWN_ERROR';
  const userMessage = errorData.user_message || error?.message || 'An error occurred';
  const actionRequired = errorData.action_required;
  const details = errorData.details || {};
  const failures: ErrorFailure[] = details.failures || [];
  const summary = details.summary || {};
  const stage = details.stage;

  const getErrorIcon = (errorType: string) => {
    switch (errorType) {
      case 'NIFI_DEPLOYMENT_FAILED':
        return <BugOutlined style={{ color: '#ff4d4f' }} />;
      case 'WORKFLOW_STAGE_FAILED':
        return <ToolOutlined style={{ color: '#faad14' }} />;
      default:
        return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />;
    }
  };

  const getComponentTypeColor = (componentType: string) => {
    switch (componentType) {
      case 'processor':
        return 'blue';
      case 'connection':
        return 'green';
      case 'deployment':
        return 'red';
      default:
        return 'default';
    }
  };

  const renderFailureDetails = (failure: ErrorFailure, index: number) => {
    const hasDetails = failure.details && Object.keys(failure.details).length > 0;
    
    return (
      <div key={index} style={{ marginBottom: 12, padding: 12, border: '1px solid #f0f0f0', borderRadius: 6 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Space>
            <Tag color={getComponentTypeColor(failure.component_type)}>
              {failure.component_type.toUpperCase()}
            </Tag>
            <Text strong>{failure.component_name}</Text>
            <Tag color="orange">{failure.error_type}</Tag>
          </Space>
          
          <Text type="danger">{failure.message}</Text>
          
          {hasDetails && (
            <Collapse size="small" ghost>
              <Panel header="Technical Details" key="details">
                <pre style={{ 
                  background: '#f6f8fa', 
                  padding: 8, 
                  borderRadius: 4, 
                  fontSize: 12,
                  overflow: 'auto'
                }}>
                  {JSON.stringify(failure.details, null, 2)}
                </pre>
              </Panel>
            </Collapse>
          )}
        </Space>
      </div>
    );
  };

  return (
    <div>
      <Alert
        message={title}
        description={
          <Space direction="vertical" style={{ width: '100%' }}>
            <Space>
              {getErrorIcon(errorType)}
              <Text strong>{userMessage}</Text>
            </Space>
            
            {actionRequired && (
              <Paragraph style={{ margin: 0 }}>
                <Text type="warning">Action Required: </Text>
                <Text>{actionRequired}</Text>
              </Paragraph>
            )}
            
            {stage && (
              <Text type="secondary">Failed at stage: <Text code>{stage}</Text></Text>
            )}
          </Space>
        }
        type="error"
        showIcon={false}
        style={{ marginBottom: 16 }}
      />

      {Object.keys(summary).length > 0 && (
        <>
          <Text strong>Deployment Summary:</Text>
          <div style={{ marginLeft: 16, marginBottom: 16 }}>
            {summary.total_processors !== undefined && (
              <div>Processors: {summary.created_processors || 0} created, {summary.failed_processors || 0} failed (out of {summary.total_processors})</div>
            )}
            {summary.total_connections !== undefined && (
              <div>Connections: {summary.created_connections || 0} created, {summary.failed_connections || 0} failed (out of {summary.total_connections})</div>
            )}
          </div>
          <Divider />
        </>
      )}

      {failures.length > 0 && (
        <>
          <Text strong>Component Failures ({failures.length}):</Text>
          <div style={{ marginTop: 8 }}>
            {failures.map((failure, index) => renderFailureDetails(failure, index))}
          </div>
        </>
      )}

      {failures.length === 0 && Object.keys(summary).length === 0 && (
        <Text type="secondary">No additional error details available.</Text>
      )}
    </div>
  );
};