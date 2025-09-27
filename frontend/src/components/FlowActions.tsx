import React from 'react';
import { Form, Input, Button, Space } from 'antd';
import { RocketOutlined, SaveOutlined } from '@ant-design/icons';
const { TextArea } = Input;

interface FlowActionsProps {
  flowName: string;
  flowDescription: string;
  onFlowNameChange: (name: string) => void;
  onFlowDescriptionChange: (description: string) => void;
  onDeploy: () => void;
  onSave?: () => void;
  deployLoading?: boolean;
  saveLoading?: boolean;
  canDeploy?: boolean;
  canSave?: boolean;
}

export const FlowActions: React.FC<FlowActionsProps> = ({
  flowName,
  flowDescription,
  onFlowNameChange,
  onFlowDescriptionChange,
  onDeploy,
  onSave,
  deployLoading = false,
  saveLoading = false,
  canDeploy = true,
  canSave = true
}) => {
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
        <Form.Item
          label="Flow Name"
          style={{ marginBottom: '12px' }}
          required
        >
          <Input
            value={flowName}
            onChange={(e) => onFlowNameChange(e.target.value)}
            placeholder="Enter flow name"
            disabled={deployLoading}
          />
        </Form.Item>

        <Form.Item
          label="Description"
          style={{ marginBottom: '16px' }}
        >
          <TextArea
            value={flowDescription}
            onChange={(e) => onFlowDescriptionChange(e.target.value)}
            placeholder="Enter flow description"
            rows={3}
            disabled={deployLoading}
          />
        </Form.Item>

        <Space direction="vertical" style={{ width: '100%' }}>
          {onSave && (
            <Button
              icon={<SaveOutlined />}
              onClick={onSave}
              loading={saveLoading}
              disabled={!canSave || deployLoading}
              style={{ width: '100%' }}
            >
              Save Draft
            </Button>
          )}

          <Button
            type="primary"
            icon={<RocketOutlined />}
            onClick={onDeploy}
            loading={deployLoading}
            disabled={!canDeploy || !flowName.trim()}
            size="large"
            style={{ width: '100%' }}
          >
            Deploy Flow
          </Button>
        </Space>
    </Space>
  );
};