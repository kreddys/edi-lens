import React from 'react';
import { Card, Typography, Input } from 'antd';
import { CodeOutlined } from '@ant-design/icons';

const { TextArea } = Input;
const { Text } = Typography;

interface FlowJsonEditorProps {
  value: string;
  onChange: (value: string) => void;
  error?: string;
  loading?: boolean;
  extra?: React.ReactNode;
}

export const FlowJsonEditor: React.FC<FlowJsonEditorProps> = ({
  value,
  onChange,
  error,
  loading = false,
  extra
}) => {
  return (
    <Card
      title={
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CodeOutlined />
            <Text strong>Flow Definition (JSON)</Text>
          </div>
          {extra && <div>{extra}</div>}
        </div>
      }
      style={{ height: '100%' }}
      bodyStyle={{ 
        padding: '16px',
        height: 'calc(100% - 57px)', // Account for header height
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      <TextArea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          fontFamily: 'Consolas, Monaco, "Courier New", monospace',
          fontSize: '13px',
          lineHeight: '1.5',
          flex: 1,
          resize: 'none'
        }}
        placeholder="Enter your flow definition in JSON format..."
        disabled={loading}
        status={error ? 'error' : undefined}
      />
      {error && (
        <div style={{ marginTop: '8px' }}>
          <Text type="danger" style={{ fontSize: '12px' }}>
            {error}
          </Text>
        </div>
      )}
    </Card>
  );
};