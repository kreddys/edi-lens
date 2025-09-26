import React, { useState, useEffect } from "react";
import { Table, Space, Button, Typography, Modal, Form, Input, Select, notification } from "antd";
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  DeleteOutlined,
  PlusOutlined,
  EyeOutlined,
  ReloadOutlined,
  EditOutlined
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

interface RegistryFlow {
  flow_id: string;
  bucket_id: string;
  name: string;
  description: string;
  type: string;
  created_timestamp: number;
  modified_timestamp: number;
  version_count: number;
}

export const FlowsList: React.FC = () => {
  const [flows, setFlows] = useState<Flow[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [deployModalVisible, setDeployModalVisible] = useState(false);
  const [selectedFlow, setSelectedFlow] = useState<string | null>(null);
  const [buckets, setBuckets] = useState<any[]>([]);
  const [selectedBucketFlows, setSelectedBucketFlows] = useState<RegistryFlow[]>([]);
  const [selectedBucketId, setSelectedBucketId] = useState<string>('');
  const [selectedFlowId, setSelectedFlowId] = useState<string>('');
  const [flowVersions, setFlowVersions] = useState<any[]>([]);
  const [form] = Form.useForm();
  const [createForm] = Form.useForm();

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

  const loadBuckets = async () => {
    try {
      const bucketsData = await flowAPI.listBuckets();
      const bucketArray = Array.isArray(bucketsData) ? bucketsData : [];

      // If no buckets exist, create a default one
      if (bucketArray.length === 0) {
        try {
          const defaultBucket = await flowAPI.createBucket(
            'default-flows',
            'Default bucket for flow storage'
          );
          setBuckets([defaultBucket]);
          notification.success({
            message: 'Default Bucket Created',
            description: 'Created default bucket for storing flows.'
          });
        } catch (createError) {
          console.error('Failed to create default bucket:', createError);
          setBuckets([]);
          notification.warning({
            message: 'No Buckets Available',
            description: 'No registry buckets found and failed to create default bucket. Contact administrator.'
          });
        }
      } else {
        setBuckets(bucketArray);
      }
    } catch (error) {
      console.error('Failed to load buckets:', error);
      setBuckets([]);
      notification.error({
        message: 'Backend Connection Error',
        description: 'Could not connect to the backend API. Make sure the backend is running on port 8000.'
      });
    }
  };

  useEffect(() => {
    loadBuckets();
    loadDeployedFlows();
  }, []);

  const refreshData = () => {
    loadDeployedFlows();
  };

  const loadFlowsForBucket = async (bucketId: string) => {
    if (!bucketId) {
      setSelectedBucketFlows([]);
      return;
    }

    try {
      const flows = await flowAPI.listFlowsInBucket(bucketId);
      setSelectedBucketFlows(flows);
    } catch (error) {
      console.error('Failed to load flows for bucket:', error);
      setSelectedBucketFlows([]);
    }
  };

  const loadVersionsForFlow = async (bucketId: string, flowId: string) => {
    if (!bucketId || !flowId) {
      setFlowVersions([]);
      return;
    }

    try {
      const versions = await flowAPI.getFlowVersions(bucketId, flowId);
      setFlowVersions(versions);
    } catch (error) {
      console.error('Failed to load versions for flow:', error);
      setFlowVersions([]);
    }
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

      // Ensure the flow definition has required fields
      if (!flowDefinition.name) {
        flowDefinition.name = values.flowName;
      }
      if (!flowDefinition.description) {
        flowDefinition.description = values.description || '';
      }

      await flowAPI.deployAndStore(flowDefinition, values.bucketId, {});

      notification.success({
        message: 'Success',
        description: 'Flow created and deployed successfully'
      });

      setCreateModalVisible(false);
      createForm.resetFields();
      refreshData();
    } catch (error) {
      notification.error({
        message: 'Error',
        description: 'Failed to create flow'
      });
    }
  };

  const handleDeployFromRegistry = async (values: any) => {
    try {
      const version = values.version === 'latest' ? undefined : parseInt(values.version);
      const flowData = await flowAPI.getFlowFromRegistry(
        values.bucketId,
        values.flowId,
        version
      );

      await flowAPI.deployAndStore(flowData, values.bucketId, {});

      notification.success({
        message: 'Success',
        description: 'Flow deployed from registry successfully'
      });

      setDeployModalVisible(false);
      form.resetFields();
      setSelectedBucketId('');
      setSelectedFlowId('');
      setSelectedBucketFlows([]);
      setFlowVersions([]);
      refreshData();
    } catch (error) {
      notification.error({
        message: 'Error',
        description: 'Failed to deploy flow from registry'
      });
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
            icon={<EditOutlined />}
            onClick={() => setDeployModalVisible(true)}
          >
            Deploy from Registry
          </Button>
          <Button
            icon={<ReloadOutlined />}
            onClick={refreshData}
            loading={loading}
          >
            Refresh
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateModalVisible(true)}
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
          createForm.resetFields();
        }}
        footer={null}
        width={800}
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={handleCreateFlow}
          initialValues={{
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
            name="bucketId"
            label="Registry Bucket"
            rules={[{ required: true, message: 'Please select a bucket' }]}
          >
            <Select placeholder="Select a bucket">
              {buckets && buckets.length > 0 ? (
                buckets.map(bucket => (
                  <Option key={bucket.bucket_id} value={bucket.bucket_id}>
                    {bucket.bucket_name}
                  </Option>
                ))
              ) : (
                <Option disabled value="">No buckets available</Option>
              )}
            </Select>
          </Form.Item>

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
                createForm.resetFields();
              }}>
                Cancel
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Deploy from Registry Modal */}
      <Modal
        title="Deploy Flow from Registry"
        open={deployModalVisible}
        onCancel={() => {
          setDeployModalVisible(false);
          form.resetFields();
          setSelectedBucketId('');
          setSelectedFlowId('');
          setSelectedBucketFlows([]);
          setFlowVersions([]);
        }}
        footer={null}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleDeployFromRegistry}
        >
          <Form.Item
            name="bucketId"
            label="Registry Bucket"
            rules={[{ required: true, message: 'Please select a bucket' }]}
          >
            <Select
              placeholder="Select a bucket"
              onChange={(value) => {
                setSelectedBucketId(value);
                loadFlowsForBucket(value);
                form.setFieldValue('flowId', undefined);
              }}
            >
              {buckets && buckets.length > 0 ? (
                buckets.map(bucket => (
                  <Option key={bucket.bucket_id} value={bucket.bucket_id}>
                    {bucket.bucket_name}
                  </Option>
                ))
              ) : (
                <Option disabled value="">No buckets available</Option>
              )}
            </Select>
          </Form.Item>

          <Form.Item
            name="flowId"
            label="Flow"
            rules={[{ required: true, message: 'Please select a flow' }]}
          >
            <Select
              placeholder="Select a flow"
              disabled={!selectedBucketId}
              onChange={(value) => {
                setSelectedFlowId(value);
                loadVersionsForFlow(selectedBucketId, value);
                form.setFieldValue('version', undefined);
              }}
            >
              {selectedBucketFlows.length > 0 ? (
                selectedBucketFlows.map(flow => (
                  <Option key={flow.flow_id} value={flow.flow_id}>
                    {flow.name} - {flow.description}
                  </Option>
                ))
              ) : (
                <Option disabled value="">No flows available in selected bucket</Option>
              )}
            </Select>
          </Form.Item>

          <Form.Item
            name="version"
            label="Version"
            rules={[{ required: true, message: 'Please select a version' }]}
          >
            <Select placeholder="Select version" disabled={!selectedFlowId}>
              <Option value="latest">Latest Version</Option>
              {flowVersions.map(version => (
                <Option key={version.version || version.version_number} value={version.version || version.version_number}>
                  Version {version.version || version.version_number} - {version.comments || 'No description'}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                Deploy
              </Button>
              <Button onClick={() => {
                setDeployModalVisible(false);
                form.resetFields();
                setSelectedBucketId('');
                setSelectedFlowId('');
                setSelectedBucketFlows([]);
                setFlowVersions([]);
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