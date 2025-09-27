import React from 'react';
import { Radio, Select, Input, Form, Typography, Space } from 'antd';
import { PlusOutlined } from '@ant-design/icons';

const { Text } = Typography;
const { Option } = Select;

interface Bucket {
  bucket_id: string;
  bucket_name: string;
  description?: string;
}

interface BucketSelectorProps {
  buckets: Bucket[];
  mode: 'select' | 'create';
  selectedBucketId?: string;
  newBucketName?: string;
  newBucketDescription?: string;
  onModeChange: (mode: 'select' | 'create') => void;
  onBucketSelect: (bucketId: string) => void;
  onNewBucketNameChange: (name: string) => void;
  onNewBucketDescriptionChange: (description: string) => void;
  loading?: boolean;
}

export const BucketSelector: React.FC<BucketSelectorProps> = ({
  buckets,
  mode,
  selectedBucketId,
  newBucketName,
  newBucketDescription,
  onModeChange,
  onBucketSelect,
  onNewBucketNameChange,
  onNewBucketDescriptionChange,
  loading = false
}) => {
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
        <Radio.Group
          value={mode}
          onChange={(e) => onModeChange(e.target.value)}
          style={{ width: '100%' }}
        >
          {buckets.length > 0 && (
            <Radio value="select" style={{ width: '100%', marginBottom: '8px' }}>
              Use existing bucket
            </Radio>
          )}
          <Radio value="create">
            <Space>
              <PlusOutlined />
              Create new bucket
            </Space>
          </Radio>
        </Radio.Group>

        {mode === 'select' && buckets.length > 0 && (
          <Form.Item
            label="Select Bucket"
            style={{ marginBottom: '8px' }}
          >
            <Select
              value={selectedBucketId}
              onChange={onBucketSelect}
              placeholder="Choose a bucket"
              disabled={loading}
              style={{ width: '100%' }}
              optionLabelProp="label"
            >
              {buckets.map(bucket => (
                <Option 
                  key={bucket.bucket_id} 
                  value={bucket.bucket_id}
                  label={bucket.bucket_name}
                >
                  <div>
                    <div style={{ fontWeight: 500 }}>{bucket.bucket_name}</div>
                    {bucket.description && (
                      <Text type="secondary" style={{ fontSize: '12px' }}>
                        {bucket.description}
                      </Text>
                    )}
                  </div>
                </Option>
              ))}
            </Select>
          </Form.Item>
        )}

        {mode === 'create' && (
          <>
            <Form.Item
              label="Bucket Name"
              style={{ marginBottom: '8px' }}
              required
            >
              <Input
                value={newBucketName}
                onChange={(e) => onNewBucketNameChange(e.target.value)}
                placeholder="Enter bucket name"
                disabled={loading}
              />
            </Form.Item>
            <Form.Item
              label="Description"
              style={{ marginBottom: '0' }}
            >
              <Input
                value={newBucketDescription}
                onChange={(e) => onNewBucketDescriptionChange(e.target.value)}
                placeholder="Optional description"
                disabled={loading}
              />
            </Form.Item>
            <Text type="secondary" style={{ fontSize: '12px' }}>
              Bucket names must be unique in the NiFi Registry
            </Text>
          </>
        )}
    </Space>
  );
};