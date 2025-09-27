import { useState, useEffect, forwardRef, useImperativeHandle } from "react";
import { Table, Space, Button, Typography, notification, Modal } from "antd";
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  DeleteOutlined,
  EyeOutlined,
  PlusOutlined
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { flowAPI } from "../../providers/data";
import { FlowDetail } from "./FlowDetail";

const { Text } = Typography;

interface Flow {
  id: string;
  name: string;
  description: string;
  status: string;
  deployment_status: string;
  processor_count: number;
  running_count: number;
  stopped_count: number;
  invalid_count: number;
  created_at?: string;
  updated_at?: string;
  version_control?: {
    state: string;
    version: number;
    local_modifications: boolean;
  };
}

// Registry bucket interface moved to FlowDesigner

interface FlowsListProps {
  onEditFlow?: (flowId: string) => void;
}

interface FlowsListRef {
  refreshFlows: () => void;
}

export const FlowsList = forwardRef<FlowsListRef, FlowsListProps>(({ onEditFlow }, ref) => {
  const [flows, setFlows] = useState<Flow[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedFlow, setSelectedFlow] = useState<string | null>(null);
  const navigate = useNavigate();

  const loadDeployedFlows = async () => {
    setLoading(true);
    try {
      const response = await flowAPI.listFlows();
      setFlows(response.flows || []);
    } catch (error) {
      console.error('Failed to load flows:', error);
      notification.error({
        message: 'Error',
        description: 'Failed to load deployed flows'
      });
    } finally {
      setLoading(false);
    }
  };

  // Buckets loading removed - now handled in FlowDesigner

  useEffect(() => {
    loadDeployedFlows();
  }, []);

  // Expose refresh function to parent component
  useImperativeHandle(ref, () => ({
    refreshFlows: loadDeployedFlows
  }));

  const refreshData = () => {
    loadDeployedFlows();
  };

  const handleStartFlow = async (flowId: string) => {
    try {
      await flowAPI.startFlow(flowId);
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

  const handleStopFlow = async (flowId: string) => {
    try {
      await flowAPI.stopFlow(flowId);
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

  const handleDeleteFlow = async (flowId: string) => {
    Modal.confirm({
      title: 'Delete Flow',
      content: 'Are you sure you want to delete this flow?',
      onOk: async () => {
        try {
          await flowAPI.deleteFlow(flowId);
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

  // Flow creation moved to FlowDesigner component

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
    <div style={{ padding: '24px' }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography.Title level={2} style={{ margin: 0 }}>
          Flows
        </Typography.Title>
        <Button 
          type="primary" 
          icon={<PlusOutlined />}
          onClick={() => navigate('/flows/create')}
        >
          Create New Flow
        </Button>
      </div>

      {flows.length > 0 ? (
        <Table
          dataSource={flows}
          rowKey="id"
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
                  onClick={() => navigate(`/flows/${record.id}`)}
                  title={onEditFlow ? "Edit Flow" : "View Details"}
                />
                {record.status === 'RUNNING' ? (
                  <Button
                    type="text"
                    icon={<PauseCircleOutlined />}
                    onClick={() => handleStopFlow(record.id)}
                  />
                ) : (
                  <Button
                    type="text"
                    icon={<PlayCircleOutlined />}
                    onClick={() => handleStartFlow(record.id)}
                  />
                )}
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => handleDeleteFlow(record.id)}
                />
              </Space>
            )}
          />
        </Table>
      ) : (
        <div style={{ textAlign: 'center', padding: '48px' }}>
          <Typography.Text type="secondary">
            No flows created yet. Click "Create New Flow" to get started.
          </Typography.Text>
        </div>
      )}
    </div>
  );
});
