import React, { useState, useEffect } from "react";
import {
  Show,
} from "@refinedev/antd";
import {
  Card,
  Row,
  Col,
  Typography,
  Tag,
  Space,
  Divider,
  Button,
  Statistic,
  Progress,
  Descriptions,
  Spin,
  Alert
} from "antd";
import {
  PlayCircleOutlined,
  CheckCircleOutlined,
} from "@ant-design/icons";
import { IResourceComponentsProps, useOne } from "@refinedev/core";
import { WorkflowStatusBadge, DeploymentBadge } from "../../components/workflow/StatusBadges";
import { WorkflowControl } from "../../components/workflow/WorkflowControl";

const { Text } = Typography;

export const WorkflowShow: React.FC<IResourceComponentsProps> = () => {
  const [workflowStatus, setWorkflowStatus] = useState<any>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);

  // Get the workflow ID from the URL params
  const urlParams = new URLSearchParams(window.location.search);
  const workflowId = urlParams.get("id") || "";

  // Fetch workflow data
  const { data, isLoading } = useOne({
    resource: "workflows",
    id: workflowId,
  });
  const record = data?.data;

  // Fetch workflow status
  useEffect(() => {
    if (record?.workflow_id) {
      fetchWorkflowStatus(record.workflow_id);
    }
  }, [record?.workflow_id]);

  const fetchWorkflowStatus = async (workflowId: string) => {
    setLoadingStatus(true);
    try {
      // In a real implementation, this would call the workflow status API
      // GET /api/v1/workflows/{workflow_id}/status
      // const response = await fetch(`/api/v1/workflows/${workflowId}/status`, {
      //   headers: {
      //     "Authorization": `Bearer ${localStorage.getItem("auth_token")}`
      //   }
      // });
      // 
      // if (!response.ok) {
      //   throw new Error(`HTTP error! status: ${response.status}`);
      // }
      // 
      // const statusData = await response.json();
      // setWorkflowStatus(statusData);
      
      // For now, we'll use mock data
      setWorkflowStatus({
        workflow_id: workflowId,
        status: record?.status || "ACTIVE",
        nifi_status: "RUNNING",
        deployment_status: "DEPLOYED",
        last_execution: new Date().toISOString(),
        execution_count: 42,
        error_count: 3,
        success_rate: 0.93,
        process_group_id: "process-group-123",
        parameter_context_id: "param-context-456",
        flow_version: 3,
        health_check: {
          status: "healthy",
          last_check: new Date().toISOString(),
          issues: []
        }
      });
    } catch (error) {
      console.error("Failed to fetch workflow status:", error);
    } finally {
      setLoadingStatus(false);
    }
  };

  const handleActionComplete = () => {
    // Refresh workflow data and status after an action
    // In a real implementation, you would refetch the data
    // For now, we'll just refetch the status
    if (record?.workflow_id) {
      fetchWorkflowStatus(record.workflow_id);
    }
  };

  if (isLoading) {
    return (
      <div style={{ textAlign: "center", padding: "40px" }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>
          <Text>Loading workflow details...</Text>
        </div>
      </div>
    );
  }

  return (
    <Show isLoading={isLoading}>
      <Row gutter={[24, 24]}>
        <Col xs={24} lg={16}>
          <Card title="Workflow Information" size="small">
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="Name">
                <Text strong>{record?.name}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Status">
                <WorkflowStatusBadge status={record?.status} />
              </Descriptions.Item>
              <Descriptions.Item label="Description" span={2}>
                <Text>{record?.description || "No description provided"}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Template">
                <Text code>{record?.template_id}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Deployment">
                <DeploymentBadge isDeployed={record?.is_deployed} />
              </Descriptions.Item>
            </Descriptions>
          </Card>

          <Card title="Configuration" size="small" style={{ marginTop: 16 }}>
            <pre style={{ 
              background: "#f5f5f5", 
              padding: 16, 
              borderRadius: 4,
              fontSize: 12,
              overflowX: "auto",
              maxHeight: 300
            }}>
              {JSON.stringify(record?.configuration, null, 2)}
            </pre>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="Actions" size="small">
            <WorkflowControl
              workflowId={record?.workflow_id}
              isDeployed={record?.is_deployed}
              status={record?.status}
              onActionComplete={handleActionComplete}
            />
            
            <Divider style={{ margin: "16px 0" }} />
            
            <Button 
              type="primary" 
              icon={<PlayCircleOutlined />}
              block
            >
              Execute Workflow
            </Button>
          </Card>

          <Card title="Monitoring" size="small" style={{ marginTop: 16 }}>
            {loadingStatus ? (
              <div style={{ textAlign: "center", padding: "20px" }}>
                <Spin />
              </div>
            ) : workflowStatus ? (
              <Space direction="vertical" style={{ width: "100%" }}>
                <Row gutter={[16, 16]}>
                  <Col span={12}>
                    <Statistic
                      title="Success Rate"
                      value={workflowStatus.success_rate * 100}
                      precision={1}
                      suffix="%"
                      valueStyle={{ color: workflowStatus.success_rate > 0.9 ? "#3f8600" : "#cf1322" }}
                    />
                    <Progress percent={workflowStatus.success_rate * 100} showInfo={false} size="small" />
                  </Col>
                  <Col span={12}>
                    <Statistic
                      title="Executions"
                      value={workflowStatus.execution_count}
                      prefix={<CheckCircleOutlined />}
                    />
                  </Col>
                </Row>
                
                <Divider style={{ margin: "8px 0" }} />
                
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="NiFi Status">
                    <Tag color={workflowStatus.nifi_status === "RUNNING" ? "success" : "warning"}>
                      {workflowStatus.nifi_status}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="Errors">
                    <Text type={workflowStatus.error_count > 0 ? "danger" : "success"}>
                      {workflowStatus.error_count}
                    </Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="Flow Version">
                    <Tag>{workflowStatus.flow_version}</Tag>
                  </Descriptions.Item>
                </Descriptions>
              </Space>
            ) : (
              <Alert
                message="Status Unavailable"
                description="Unable to fetch workflow status information"
                type="warning"
                showIcon
              />
            )}
          </Card>
        </Col>
      </Row>
    </Show>
  );
};