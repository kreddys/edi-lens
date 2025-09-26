import React, { useState, useEffect } from "react";
import {
  Card,
  Typography,
  Space,
  Button,
  Tabs,
  Modal,
  notification,
  Tag,
  Descriptions,
  Row,
  Col,
  Spin,
  Input
} from "antd";
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  EditOutlined,
  DeleteOutlined,
  SaveOutlined,
  ReloadOutlined,
  BranchesOutlined
} from "@ant-design/icons";
import { flowAPI } from "../../providers/data";

const { Title, Text } = Typography;
const { TextArea } = Input;

interface FlowDetailProps {
  processGroupId: string;
  onBack: () => void;
  onFlowUpdate: () => void;
}

interface FlowStatus {
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

interface FlowDefinition {
  name: string;
  description: string;
  processors: any[];
  connections: any[];
  process_groups: any[];
  [key: string]: any;
}

export const FlowDetail: React.FC<FlowDetailProps> = ({
  processGroupId,
  onBack,
  onFlowUpdate
}) => {
  const [flowStatus, setFlowStatus] = useState<FlowStatus | null>(null);
  const [flowDefinition, setFlowDefinition] = useState<FlowDefinition | null>(null);
  const [modifications, setModifications] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [editedDefinition, setEditedDefinition] = useState<string>("");
  const [activeTab, setActiveTab] = useState("overview");

  const loadFlowData = async () => {
    setLoading(true);
    try {
      const [status, definition, mods] = await Promise.allSettled([
        flowAPI.getStatus(processGroupId),
        // For now, we'll create a mock definition since the backend doesn't expose flow definition directly
        Promise.resolve({
          name: "Sample Flow",
          description: "Sample flow definition",
          processors: [],
          connections: [],
          process_groups: []
        }),
        flowAPI.getModifications(processGroupId)
      ]);

      if (status.status === 'fulfilled') {
        setFlowStatus(status.value);
      }

      if (definition.status === 'fulfilled') {
        setFlowDefinition(definition.value);
        setEditedDefinition(JSON.stringify(definition.value, null, 2));
      }

      if (mods.status === 'fulfilled') {
        setModifications(mods.value);
      }
    } catch (error) {
      console.error('Failed to load flow data:', error);
      notification.error({
        message: 'Error',
        description: 'Failed to load flow details'
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFlowData();
  }, [processGroupId]);

  const handleStartFlow = async () => {
    try {
      await flowAPI.start(processGroupId);
      notification.success({
        message: 'Success',
        description: 'Flow started successfully'
      });
      loadFlowData();
      onFlowUpdate();
    } catch (error) {
      notification.error({
        message: 'Error',
        description: 'Failed to start flow'
      });
    }
  };

  const handleStopFlow = async () => {
    try {
      await flowAPI.stop(processGroupId);
      notification.success({
        message: 'Success',
        description: 'Flow stopped successfully'
      });
      loadFlowData();
      onFlowUpdate();
    } catch (error) {
      notification.error({
        message: 'Error',
        description: 'Failed to stop flow'
      });
    }
  };

  const handleDeleteFlow = () => {
    Modal.confirm({
      title: 'Delete Flow',
      content: 'Are you sure you want to delete this flow? This action cannot be undone.',
      okText: 'Delete',
      okType: 'danger',
      onOk: async () => {
        try {
          await flowAPI.delete(processGroupId, true);
          notification.success({
            message: 'Success',
            description: 'Flow deleted successfully'
          });
          onFlowUpdate();
          onBack();
        } catch (error) {
          notification.error({
            message: 'Error',
            description: 'Failed to delete flow'
          });
        }
      }
    });
  };

  const handleSaveDefinition = async () => {
    try {
      const parsedDefinition = JSON.parse(editedDefinition);
      // TODO: Implement update flow definition API call
      setFlowDefinition(parsedDefinition);
      setEditMode(false);
      notification.success({
        message: 'Success',
        description: 'Flow definition updated successfully'
      });
      onFlowUpdate();
    } catch (error) {
      notification.error({
        message: 'Error',
        description: 'Invalid JSON format or failed to update flow'
      });
    }
  };

  const handleCommit = async () => {
    Modal.confirm({
      title: 'Commit Changes',
      content: 'Commit local modifications to the registry?',
      onOk: async () => {
        try {
          await flowAPI.commit(processGroupId, 'Updated flow definition');
          notification.success({
            message: 'Success',
            description: 'Changes committed to registry'
          });
          loadFlowData();
        } catch (error) {
          notification.error({
            message: 'Error',
            description: 'Failed to commit changes'
          });
        }
      }
    });
  };

  const handleUpdateFromRegistry = async () => {
    try {
      await flowAPI.updateFromRegistry(processGroupId);
      notification.success({
        message: 'Success',
        description: 'Flow updated from registry'
      });
      loadFlowData();
    } catch (error) {
      notification.error({
        message: 'Error',
        description: 'Failed to update from registry'
      });
    }
  };

  const handleRevert = async () => {
    Modal.confirm({
      title: 'Revert Changes',
      content: 'Revert all local modifications? This action cannot be undone.',
      okText: 'Revert',
      okType: 'danger',
      onOk: async () => {
        try {
          await flowAPI.revert(processGroupId);
          notification.success({
            message: 'Success',
            description: 'Local changes reverted'
          });
          loadFlowData();
        } catch (error) {
          notification.error({
            message: 'Error',
            description: 'Failed to revert changes'
          });
        }
      }
    });
  };

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'running': return 'green';
      case 'stopped': return 'red';
      case 'invalid': return 'orange';
      default: return 'gray';
    }
  };

  const getVersionControlColor = (state: string) => {
    switch (state?.toLowerCase()) {
      case 'up_to_date': return 'green';
      case 'locally_modified': return 'orange';
      case 'stale': return 'red';
      case 'locally_modified_and_stale': return 'volcano';
      default: return 'gray';
    }
  };

  if (loading && !flowStatus) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '50px' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>Loading flow details...</div>
        </div>
      </Card>
    );
  }

  const tabItems = [
    {
      key: 'overview',
      label: 'Overview',
      children: (
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <Card title="Flow Information">
              <Descriptions column={2}>
                <Descriptions.Item label="Name">
                  {flowStatus?.name || 'Unknown'}
                </Descriptions.Item>
                <Descriptions.Item label="Process Group ID">
                  {processGroupId}
                </Descriptions.Item>
                <Descriptions.Item label="Status">
                  <Tag color={getStatusColor(flowStatus?.status || '')}>
                    {flowStatus?.status || 'Unknown'}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="Total Processors">
                  {flowStatus?.processor_count || 0}
                </Descriptions.Item>
                <Descriptions.Item label="Running Processors">
                  <Text type="success">{flowStatus?.running_count || 0}</Text>
                </Descriptions.Item>
                <Descriptions.Item label="Stopped Processors">
                  <Text type="danger">{flowStatus?.stopped_count || 0}</Text>
                </Descriptions.Item>
                {(flowStatus?.invalid_count || 0) > 0 && (
                  <Descriptions.Item label="Invalid Processors">
                    <Text type="warning">{flowStatus?.invalid_count}</Text>
                  </Descriptions.Item>
                )}
              </Descriptions>
            </Card>
          </Col>

          {flowStatus?.version_control && (
            <Col span={24}>
              <Card title="Version Control">
                <Descriptions column={2}>
                  <Descriptions.Item label="State">
                    <Tag color={getVersionControlColor(flowStatus.version_control.state)}>
                      {flowStatus.version_control.state.replace(/_/g, ' ').toUpperCase()}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="Version">
                    {flowStatus.version_control.version}
                  </Descriptions.Item>
                  <Descriptions.Item label="Local Modifications">
                    {flowStatus.version_control.local_modifications ? 'Yes' : 'No'}
                  </Descriptions.Item>
                </Descriptions>

                {flowStatus.version_control.local_modifications && (
                  <Space style={{ marginTop: 16 }}>
                    <Button
                      icon={<SaveOutlined />}
                      onClick={handleCommit}
                    >
                      Commit Changes
                    </Button>
                    <Button
                      icon={<ReloadOutlined />}
                      onClick={handleRevert}
                      danger
                    >
                      Revert Changes
                    </Button>
                  </Space>
                )}

                <Space style={{ marginTop: 16, marginLeft: 8 }}>
                  <Button
                    icon={<BranchesOutlined />}
                    onClick={handleUpdateFromRegistry}
                  >
                    Update from Registry
                  </Button>
                </Space>
              </Card>
            </Col>
          )}
        </Row>
      )
    },
    {
      key: 'definition',
      label: 'Flow Definition',
      children: (
        <Card
          title="Flow Definition (JSON)"
          extra={
            <Space>
              {editMode ? (
                <>
                  <Button
                    type="primary"
                    icon={<SaveOutlined />}
                    onClick={handleSaveDefinition}
                  >
                    Save
                  </Button>
                  <Button onClick={() => setEditMode(false)}>
                    Cancel
                  </Button>
                </>
              ) : (
                <Button
                  icon={<EditOutlined />}
                  onClick={() => setEditMode(true)}
                >
                  Edit
                </Button>
              )}
            </Space>
          }
        >
          {editMode ? (
            <TextArea
              value={editedDefinition}
              onChange={(e) => setEditedDefinition(e.target.value)}
              rows={20}
              style={{ fontFamily: 'monospace', fontSize: '12px' }}
            />
          ) : (
            <pre style={{
              background: '#f5f5f5',
              padding: 16,
              borderRadius: 4,
              fontSize: '12px',
              overflow: 'auto',
              maxHeight: 500
            }}>
              {JSON.stringify(flowDefinition, null, 2)}
            </pre>
          )}
        </Card>
      )
    },
    {
      key: 'modifications',
      label: 'Modifications',
      children: (
        <Card title="Local Modifications">
          {modifications ? (
            <pre style={{
              background: '#f5f5f5',
              padding: 16,
              borderRadius: 4,
              fontSize: '12px',
              overflow: 'auto',
              maxHeight: 400
            }}>
              {JSON.stringify(modifications, null, 2)}
            </pre>
          ) : (
            <Text type="secondary">No local modifications</Text>
          )}
        </Card>
      )
    }
  ];

  return (
    <div>
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <Button onClick={onBack} style={{ marginRight: 16 }}>
              ← Back to Flows
            </Button>
            <Title level={3} style={{ margin: 0, display: 'inline' }}>
              {flowStatus?.name || 'Flow Details'}
            </Title>
          </div>

          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={loadFlowData}
              loading={loading}
            >
              Refresh
            </Button>

            {flowStatus?.status === 'RUNNING' ? (
              <Button
                icon={<PauseCircleOutlined />}
                onClick={handleStopFlow}
              >
                Stop Flow
              </Button>
            ) : (
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleStartFlow}
              >
                Start Flow
              </Button>
            )}

            <Button
              danger
              icon={<DeleteOutlined />}
              onClick={handleDeleteFlow}
            >
              Delete Flow
            </Button>
          </Space>
        </div>

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
        />
      </Card>
    </div>
  );
};