import React, { useState, useEffect } from "react";
import { List } from "@refinedev/antd";
import { Table, Space, Button, Typography, Card, Alert, Modal, Form, Input, Select, notification } from "antd";
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  DeleteOutlined,
  PlusOutlined,
  EyeOutlined,
  ReloadOutlined
} from "@ant-design/icons";
import { flowAPI } from "../../providers/data";

const { Text, Title } = Typography;
const { Option } = Select;

interface Flow {
  process_group_id: string;
  name: string;
  status: string;
  processor_count: number;
  running_count: number;
  stopped_count: number;
  invalid_count: number;
  version_control?: any;
}

export const FlowsList: React.FC = () => {
  const [flows, setFlows] = useState<Flow[]>([]);
  const [loading, setLoading] = useState(false);
  const [deployModalVisible, setDeployModalVisible] = useState(false);
  const [buckets, setBuckets] = useState<any[]>([]);
  const [form] = Form.useForm();

  const loadFlows = async () => {
    setLoading(true);
    try {
      // For now, return empty array since we need process group IDs to get statuses
      // This will be populated when we have deployed flows
      setFlows([]);
    } catch (error) {
      console.error('Failed to load flows:', error);
      notification.error({
        message: 'Error',
        description: 'Failed to load flows'
      });
    } finally {
      setLoading(false);
    }
  };

  const loadBuckets = async () => {
    try {
      const bucketsData = await flowAPI.listBuckets();
      setBuckets(Array.isArray(bucketsData) ? bucketsData : []);
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
    loadFlows();
    loadBuckets();
  }, []);

  const handleStartFlow = async (processGroupId: string) => {
    try {
      await flowAPI.start(processGroupId);
      notification.success({
        message: 'Success',
        description: 'Flow started successfully'
      });
      loadFlows();
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
      loadFlows();
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
          loadFlows();
        } catch (error) {
          notification.error({
            message: 'Error',
            description: 'Failed to delete flow'
          });
        }
      }
    });
  };

  const handleDeployFlow = async (values: any) => {
    try {
      const flowDefinition = {
        name: values.flowName,
        description: values.description || '',
        processors: [],
        connections: [],
        process_groups: []
      };

      await flowAPI.deployAndStore(flowDefinition, values.bucketId, {});

      notification.success({
        message: 'Success',
        description: 'Flow deployed successfully'
      });

      setDeployModalVisible(false);
      form.resetFields();
      loadFlows();
    } catch (error) {
      notification.error({
        message: 'Error',
        description: 'Failed to deploy flow'
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

  return (
    <div>
      <List
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Title level={3} style={{ margin: 0 }}>NiFi Flows</Title>
            <Space>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => setDeployModalVisible(true)}
              >
                Deploy Flow
              </Button>
              <Button
                icon={<ReloadOutlined />}
                onClick={loadFlows}
                loading={loading}
              >
                Refresh
              </Button>
            </Space>
          </div>
        }
      >
        {flows.length === 0 ? (
          <Card>
            <Alert
              message="No Flows Deployed"
              description="Deploy your first flow to get started with NiFi flow management."
              type="info"
              showIcon
              action={
                <Button type="primary" onClick={() => setDeployModalVisible(true)}>
                  Deploy Flow
                </Button>
              }
            />
          </Card>
        ) : (
          <Table
            dataSource={flows}
            rowKey="process_group_id"
            loading={loading}
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
                    onClick={() => {
                      // TODO: Implement flow details view
                    }}
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
      </List>

      <Modal
        title="Deploy New Flow"
        open={deployModalVisible}
        onCancel={() => {
          setDeployModalVisible(false);
          form.resetFields();
        }}
        footer={null}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleDeployFlow}
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
            <Input.TextArea placeholder="Enter flow description" rows={3} />
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

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                Deploy
              </Button>
              <Button onClick={() => {
                setDeployModalVisible(false);
                form.resetFields();
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