import React, { useState, useEffect, useCallback } from "react";
import { Table, Space, Button, Typography, Modal, Form, Input, Select, notification, Radio } from "antd";
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  DeleteOutlined,
  PlusOutlined,
  EyeOutlined
} from "@ant-design/icons";
import { flowAPI } from "../../providers/data";
import { FlowDetail } from "./FlowDetail";

const { Text } = Typography;
const { Option } = Select;
const { TextArea } = Input;

interface Flow {
  process_group_id: string;
  name: string;
  status: string;
  processor_count: number;
  running_count: number;
  stopped_count: number;
  invalid_count: number;
  version_control?: {
    state: string;
    version: number;
    local_modifications: boolean;
  };
}

interface RegistryBucket {
  bucket_id: string;
  bucket_name: string;
  description?: string;
}

export const FlowsList: React.FC = () => {
  const [flows, setFlows] = useState<Flow[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [selectedFlow, setSelectedFlow] = useState<string | null>(null);
  const [buckets, setBuckets] = useState<RegistryBucket[]>([]);
  const [createForm] = Form.useForm();
  const bucketCount = buckets.length;
  const bucketMode = Form.useWatch<'select' | 'create'>("bucketMode", createForm) || (bucketCount === 0 ? 'create' : 'select');

  const loadDeployedFlows = async () => {
    setLoading(true);
    try {
      // For now, return empty array since we need process group IDs to get statuses
      // This will be populated when we have deployed flows with known process group IDs
      setFlows([]);
    } catch (error) {
      console.error('Failed to load deployed flows:', error);
      notification.error({
        message: 'Error',
        description: 'Failed to load deployed flows'
      });
    } finally {
      setLoading(false);
    }
  };

  const loadBuckets = async (): Promise<RegistryBucket[]> => {
    try {
      const bucketsData = await flowAPI.listBuckets();
      const bucketArray = Array.isArray(bucketsData) ? bucketsData : [];
      setBuckets(bucketArray);
      return bucketArray;
    } catch (error) {
      console.error('Failed to load buckets:', error);
      setBuckets([]);
      notification.error({
        message: 'Backend Connection Error',
        description: 'Could not connect to the backend API. Make sure the backend is running on port 8000.'
      });
      return [];
    }
  };

  const resetCreateForm = useCallback(
    (mode?: 'select' | 'create') => {
      const defaultMode = mode ?? (bucketCount === 0 ? 'create' : 'select');
      createForm.resetFields();
      createForm.setFieldsValue({
        bucketMode: defaultMode,
        bucketId: undefined,
        newBucketName: undefined,
        newBucketDescription: undefined
      });
    },
    [bucketCount, createForm]
  );

  useEffect(() => {
    loadBuckets();
    loadDeployedFlows();
  }, []);

  const refreshData = () => {
    loadDeployedFlows();
  };

  const handleStartFlow = async (processGroupId: string) => {
    try {
      await flowAPI.start(processGroupId);
      notification.success({
        message: 'Success',
        description: 'Flow started successfully'
      });
      refreshData();
    } catch (error) {
      notification.error({
        message: 'Error',
        description: 'Failed to start flow'
      });
    }
  };

  const handleStopFlow = async (processGroupId: string) => {
    try {
      await flowAPI.stop(processGroupId);
      notification.success({
        message: 'Success',
        description: 'Flow stopped successfully'
      });
      refreshData();
    } catch (error) {
      notification.error({
        message: 'Error',
        description: 'Failed to stop flow'
      });
    }
  };

  const handleDeleteFlow = async (processGroupId: string) => {
    Modal.confirm({
      title: 'Delete Flow',
      content: 'Are you sure you want to delete this flow?',
      onOk: async () => {
        try {
          await flowAPI.delete(processGroupId);
          notification.success({
            message: 'Success',
            description: 'Flow deleted successfully'
          });
          refreshData();
        } catch (error) {
          notification.error({
            message: 'Error',
            description: 'Failed to delete flow'
          });
        }
      }
    });
  };

  const handleCreateFlow = async (values: any) => {
    try {
      let flowDefinition;

      try {
        flowDefinition = JSON.parse(values.flowDefinition);
      } catch (error) {
        notification.error({
          message: 'Invalid JSON',
          description: 'Please provide a valid JSON flow definition'
        });
        return;
      }

      if (!flowDefinition.name) {
        flowDefinition.name = values.flowName;
      }
      if (!flowDefinition.description) {
        flowDefinition.description = values.description || '';
      }

      const selectedMode: 'select' | 'create' = values.bucketMode || bucketMode;
      let bucketId: string | undefined = values.bucketId;
      let createdBucketName: string | null = null;

      if (selectedMode === 'create') {
        const newBucketName = (values.newBucketName || '').trim();

        if (!newBucketName) {
          notification.error({
            message: 'Bucket Name Required',
            description: 'Enter a bucket name to create a new registry bucket.'
          });
          return;
        }

        try {
          const newBucket = await flowAPI.createBucket(newBucketName, values.newBucketDescription);
          bucketId = newBucket.bucket_id;
          createdBucketName = newBucket.bucket_name;
          setBuckets(prev => {
            const exists = prev.some(bucket => bucket.bucket_id === newBucket.bucket_id);
            return exists ? prev : [...prev, newBucket];
          });
        } catch (bucketError: any) {
          console.error('Bucket creation error:', bucketError);
          
          // Check if this has detailed error information
          const errorData = bucketError?.response?.data?.detail || {};
          const hasDetailedErrors = errorData.details?.failures?.length > 0;
          
          if (hasDetailedErrors) {
            // Import ErrorDetails component dynamically
            import('../../components/ErrorDetails').then(({ ErrorDetails }) => {
              Modal.error({
                title: 'Bucket Creation Failed',
                width: 800,
                content: React.createElement(ErrorDetails, { 
                  error: bucketError,
                  title: 'Bucket Creation Error Details'
                }),
                okText: 'Close'
              });
            });
          } else {
            // Fallback to simple notification
            const errorMessage =
              bucketError?.response?.data?.detail?.user_message ||
              bucketError?.response?.data?.detail ||
              bucketError?.message ||
              'Failed to create bucket';

            notification.error({
              message: 'Bucket Creation Failed',
              description: errorMessage
            });
          }
          return;
        }
      }

      if (!bucketId) {
        notification.error({
          message: 'Bucket Required',
          description: 'Select an existing bucket or create a new one before deploying.'
        });
        return;
      }

      await flowAPI.deployAndStore(flowDefinition, bucketId, {});

      const successDescription = createdBucketName
        ? `Flow created and deployed successfully. New bucket '${createdBucketName}' is ready for version control.`
        : 'Flow created and deployed successfully';

      notification.success({
        message: 'Success',
        description: successDescription
      });

      setCreateModalVisible(false);
      resetCreateForm('select');
      refreshData();
      if (createdBucketName) {
        loadBuckets();
      }
    } catch (error: any) {
      console.error('Flow deployment error:', error);
      
      // Check if this is a detailed deployment error
      const errorData = error?.response?.data?.detail || {};
      const hasDetailedErrors = errorData.details?.failures?.length > 0;
      
      if (hasDetailedErrors) {
        // Import ErrorDetails component dynamically
        import('../../components/ErrorDetails').then(({ ErrorDetails }) => {
          Modal.error({
            title: 'Flow Deployment Failed',
            width: 800,
            content: React.createElement(ErrorDetails, { 
              error,
              title: 'Deployment Error Details'
            }),
            okText: 'Close'
          });
        });
      } else {
        // Fallback to simple notification for non-deployment errors
        const errorMessage =
          error?.response?.data?.detail?.user_message ||
          error?.response?.data?.detail ||
          error?.message ||
          'Failed to create flow';

        notification.error({
          message: 'Error',
          description: errorMessage
        });
      }
    }
  };

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'running': return 'green';
      case 'stopped': return 'red';
      case 'invalid': return 'orange';
      default: return 'gray';
    }
  };

  if (selectedFlow) {
    return (
      <FlowDetail
        processGroupId={selectedFlow}
        onBack={() => setSelectedFlow(null)}
        onFlowUpdate={refreshData}
      />
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 16 }}>
        <Space>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={async () => {
              const currentBuckets = await loadBuckets();
              const defaultMode = currentBuckets.length === 0 ? 'create' : 'select';
              resetCreateForm(defaultMode);
              setCreateModalVisible(true);
            }}
          >
            Create
          </Button>
        </Space>
      </div>
      {flows.length > 0 && (
        <Table
          dataSource={flows}
          rowKey="process_group_id"
          loading={loading}
          showHeader={true}
        >
          <Table.Column
            title="Name"
            dataIndex="name"
            key="name"
            render={(name) => <Text strong>{name}</Text>}
          />
          <Table.Column
            title="Status"
            dataIndex="status"
            key="status"
            render={(status) => (
              <Text style={{ color: getStatusColor(status) }}>{status}</Text>
            )}
          />
          <Table.Column
            title="Processors"
            key="processors"
            render={(_, record: Flow) => (
              <Space>
                <Text>Total: {record.processor_count}</Text>
                <Text type="success">Running: {record.running_count}</Text>
                <Text type="danger">Stopped: {record.stopped_count}</Text>
                {record.invalid_count > 0 && (
                  <Text type="warning">Invalid: {record.invalid_count}</Text>
                )}
              </Space>
            )}
          />
          <Table.Column
            title="Actions"
            key="actions"
            render={(_, record: Flow) => (
              <Space>
                <Button
                  type="text"
                  icon={<EyeOutlined />}
                  onClick={() => setSelectedFlow(record.process_group_id)}
                  title="View Details"
                />
                {record.status === 'RUNNING' ? (
                  <Button
                    type="text"
                    icon={<PauseCircleOutlined />}
                    onClick={() => handleStopFlow(record.process_group_id)}
                  />
                ) : (
                  <Button
                    type="text"
                    icon={<PlayCircleOutlined />}
                    onClick={() => handleStartFlow(record.process_group_id)}
                  />
                )}
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => handleDeleteFlow(record.process_group_id)}
                />
              </Space>
            )}
          />
        </Table>
      )}

      {/* Create Flow Modal */}
      <Modal
        title="Create New Flow"
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false);
          resetCreateForm();
        }}
        footer={null}
        width={800}
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={handleCreateFlow}
          initialValues={{
            bucketMode: 'select',
            flowDefinition: JSON.stringify({
              name: "New Flow",
              description: "Description of the flow",
              processors: [],
              connections: [],
              process_groups: []
            }, null, 2)
          }}
        >
          <Form.Item
            name="flowName"
            label="Flow Name"
            rules={[{ required: true, message: 'Please enter flow name' }]}
          >
            <Input placeholder="Enter flow name" />
          </Form.Item>

          <Form.Item
            name="description"
            label="Description"
          >
            <TextArea placeholder="Enter flow description" rows={2} />
          </Form.Item>

          <Form.Item
            name="bucketMode"
            label="Registry Bucket"
            rules={[{ required: true, message: 'Please choose how to manage the bucket' }]}
          >
            <Radio.Group
              onChange={({ target: { value } }) => {
                const mode = value as 'select' | 'create';
                createForm.setFieldsValue({ bucketMode: mode });
                if (mode === 'create') {
                  createForm.setFieldsValue({ bucketId: undefined });
                } else {
                  createForm.setFieldsValue({ newBucketName: undefined, newBucketDescription: undefined });
                }
              }}
            >
              {bucketCount > 0 && (
                <Radio value="select">Use existing bucket</Radio>
              )}
              <Radio value="create">Create new bucket</Radio>
            </Radio.Group>
          </Form.Item>

          {bucketMode === 'select' && (
            <Form.Item
              name="bucketId"
              label="Select Bucket"
              rules={[{ required: true, message: 'Please select a bucket' }]}
            >
              <Select placeholder="Select a bucket" disabled={bucketCount === 0}>
                {buckets.map(bucket => (
                  <Option key={bucket.bucket_id} value={bucket.bucket_id}>
                    {bucket.bucket_name}
                  </Option>
                ))}
              </Select>
            </Form.Item>
          )}

          {bucketMode === 'create' && (
            <>
              <Form.Item
                name="newBucketName"
                label="Bucket Name"
                rules={[{ required: true, message: 'Please enter a bucket name' }]}
              >
                <Input placeholder="Enter new bucket name" />
              </Form.Item>
              <Form.Item
                name="newBucketDescription"
                label="Bucket Description"
              >
                <Input placeholder="Optional bucket description" />
              </Form.Item>
              <Text type="secondary">Bucket names must be unique in the NiFi Registry.</Text>
            </>
          )}

          <Form.Item
            name="flowDefinition"
            label="Flow Definition (JSON)"
            rules={[{ required: true, message: 'Please provide flow definition' }]}
          >
            <TextArea
              rows={12}
              placeholder="Enter flow definition in JSON format"
              style={{ fontFamily: 'monospace', fontSize: '12px' }}
            />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                Create & Deploy
              </Button>
              <Button onClick={() => {
                setCreateModalVisible(false);
                resetCreateForm();
              }}>
                Cancel
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

    </div>
  );
};
