import React from 'react';
import { Card, Alert, Typography, Space, Progress, Tag, Collapse, Divider } from 'antd';
import { 
  InfoCircleOutlined, 
  CheckCircleOutlined, 
  CloseCircleOutlined,
  BugOutlined 
} from '@ant-design/icons';

const { Text } = Typography;
const { Panel } = Collapse;

interface ValidationError {
  component_type: string;
  component_name: string;
  error_type: string;
  message: string;
  details: Record<string, any>;
}

interface FlowStatusPanelProps {
  status: 'idle' | 'validating' | 'deploying' | 'success' | 'error';
  validationErrors?: ValidationError[];
  deploymentProgress?: number;
  deploymentStage?: string;
  successMessage?: string;
  errorMessage?: string;
  errorDetails?: {
    summary?: Record<string, any>;
    failures?: ValidationError[];
    stage?: string;
  };
}

export const FlowStatusPanel: React.FC<FlowStatusPanelProps> = ({
  status,
  validationErrors = [],
  deploymentProgress,
  deploymentStage,
  successMessage,
  errorMessage,
  errorDetails
}) => {
  const getStatusIcon = () => {
    switch (status) {
      case 'success':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'error':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      case 'validating':
      case 'deploying':
        return <InfoCircleOutlined style={{ color: '#1890ff' }} />;
      default:
        return <InfoCircleOutlined style={{ color: '#8c8c8c' }} />;
    }
  };

  const getStatusTitle = () => {
    switch (status) {
      case 'validating':
        return 'Validating Flow';
      case 'deploying':
        return 'Deploying Flow';
      case 'success':
        return 'Deployment Successful';
      case 'error':
        return 'Deployment Failed';
      default:
        return 'Flow Status';
    }
  };

  const renderValidationErrors = (errors: ValidationError[]) => {
    if (errors.length === 0) return null;

    return (
      <Space direction="vertical" style={{ width: '100%' }}>
        <Text strong>Validation Issues ({errors.length}):</Text>
        {errors.map((error, index) => (
          <Card 
            key={index} 
            size="small" 
            style={{ backgroundColor: '#fff2f0', border: '1px solid #ffccc7' }}
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <Space>
                <Tag color="red">{error.component_type.toUpperCase()}</Tag>
                <Text strong>{error.component_name}</Text>
              </Space>
              <Text type="danger">{error.message}</Text>
              {error.details && Object.keys(error.details).length > 0 && (
                <Collapse ghost size="small">
                  <Panel header="Technical Details" key="details">
                    <pre style={{ 
                      fontSize: '12px', 
                      backgroundColor: '#f5f5f5', 
                      padding: '8px',
                      borderRadius: '4px',
                      margin: 0
                    }}>
                      {JSON.stringify(error.details, null, 2)}
                    </pre>
                  </Panel>
                </Collapse>
              )}
            </Space>
          </Card>
        ))}
      </Space>
    );
  };

  const renderDeploymentSummary = () => {
    if (!errorDetails?.summary) return null;

    const { summary } = errorDetails;
    return (
      <Space direction="vertical" style={{ width: '100%' }}>
        <Text strong>Deployment Summary:</Text>
        <div style={{ marginLeft: '16px' }}>
          {summary.total_processors !== undefined && (
            <div>
              <Text>Processors: </Text>
              <Tag color="green">{summary.created_processors || 0} created</Tag>
              <Tag color="red">{summary.failed_processors || 0} failed</Tag>
              <Text type="secondary">(out of {summary.total_processors})</Text>
            </div>
          )}
          {summary.total_connections !== undefined && (
            <div>
              <Text>Connections: </Text>
              <Tag color="green">{summary.created_connections || 0} created</Tag>
              <Tag color="red">{summary.failed_connections || 0} failed</Tag>
              <Text type="secondary">(out of {summary.total_connections})</Text>
            </div>
          )}
        </div>
      </Space>
    );
  };

  return (
    <Card
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {getStatusIcon()}
          <Text strong>{getStatusTitle()}</Text>
        </div>
      }
      size="small"
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        {/* Deployment Progress */}
        {(status === 'deploying' || status === 'validating') && (
          <div>
            <Progress 
              percent={deploymentProgress || 0} 
              status="active"
              size="small"
            />
            {deploymentStage && (
              <Text type="secondary" style={{ fontSize: '12px' }}>
                {deploymentStage}
              </Text>
            )}
          </div>
        )}

        {/* Success Message */}
        {status === 'success' && successMessage && (
          <Alert
            message={successMessage}
            type="success"
            showIcon
            style={{ marginBottom: '16px' }}
          />
        )}

        {/* Error Message */}
        {status === 'error' && errorMessage && (
          <Alert
            message={errorMessage}
            type="error"
            showIcon
            style={{ marginBottom: '16px' }}
          />
        )}

        {/* Deployment Summary */}
        {status === 'error' && renderDeploymentSummary()}

        {/* Error Details */}
        {status === 'error' && errorDetails?.stage && (
          <>
            <Divider style={{ margin: '12px 0' }} />
            <Text type="secondary">Failed at stage: <Text code>{errorDetails.stage}</Text></Text>
          </>
        )}

        {/* Component Failures - show either validationErrors OR errorDetails.failures, not both */}
        {((validationErrors.length > 0) || (status === 'error' && errorDetails?.failures && errorDetails.failures.length > 0)) && (
          <>
            <Divider style={{ margin: '12px 0' }} />
            {renderValidationErrors(validationErrors.length > 0 ? validationErrors : (errorDetails?.failures || []))}
          </>
        )}

        {/* Idle State */}
        {status === 'idle' && (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <BugOutlined style={{ fontSize: '24px', color: '#d9d9d9', marginBottom: '8px' }} />
            <br />
            <Text type="secondary">Configure your flow and click "Deploy" to get started</Text>
          </div>
        )}
      </Space>
    </Card>
  );
};