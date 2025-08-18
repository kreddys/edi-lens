import React from "react";
import { List, useTable } from "@refinedev/antd";
import { Table, Space, Tag, Typography, Button, Alert, notification } from "antd";
import { IResourceComponentsProps, HttpError } from "@refinedev/core";
import { EditButton, ShowButton } from "@refinedev/antd";
import { 
  PlayCircleOutlined, 
  PauseCircleOutlined, 
  RedoOutlined, 
  CloudUploadOutlined, 
  CloudDownloadOutlined 
} from "@ant-design/icons";
import { WorkflowStatusBadge, DeploymentBadge } from "../../components/workflow/StatusBadges";
import { keycloak } from "../../utils";

const { Text } = Typography;

// Define the type for our workflow
interface Workflow {
  workflow_id: string;
  name: string;
  description: string;
  template_id: string;
  status: string;
  is_deployed: boolean;
  nifi_status: string;
  tags: string[];
  configuration: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export const WorkflowList: React.FC<IResourceComponentsProps> = () => {
  const { tableProps, tableQueryResult } = useTable<Workflow, HttpError>();

  // Check if we have a data structure issue
  const hasDataStructureError = tableProps?.dataSource && !Array.isArray(tableProps.dataSource);

  // Workflow action handler
  const handleWorkflowAction = async (workflowId: string, action: string) => {
    try {
      let endpoint = "";
      switch (action) {
        case "deploy":
          endpoint = `/api/v1/workflows/${workflowId}/deploy`;
          break;
        case "undeploy":
          endpoint = `/api/v1/workflows/${workflowId}/undeploy`;
          break;
        case "pause":
          endpoint = `/api/v1/workflows/${workflowId}/pause`;
          break;
        case "resume":
          endpoint = `/api/v1/workflows/${workflowId}/resume`;
          break;
        case "restart":
          endpoint = `/api/v1/workflows/${workflowId}/restart`;
          break;
        default:
          throw new Error("Invalid action");
      }

      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${keycloak.token}`
        }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Failed to ${action} workflow`);
      }

      // Show success notification
      const actionLabels: Record<string, string> = {
        deploy: "deployed",
        undeploy: "undeployed",
        pause: "paused",
        resume: "resumed",
        restart: "restarted"
      };

      notification.success({
        message: "Success",
        description: `Workflow successfully ${actionLabels[action]}`
      });

      // Refresh the table data
      tableQueryResult.refetch();
    } catch (error: any) {
      notification.error({
        message: "Action Failed",
        description: error.message || `An error occurred while ${action}ing the workflow`
      });
      console.error(`${action} error:`, error);
    }
  };

  return (
    <List>
      {hasDataStructureError && (
        <Alert
          message="Data Structure Error"
          description={`Expected array but received ${typeof tableProps.dataSource}. Check console for details.`}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}
      <Table {...tableProps} rowKey="workflow_id">
        <Table.Column
          dataIndex="name"
          title="Name"
          render={(value, record: any) => (
            <Space direction="vertical" size={0}>
              <Text strong>{value}</Text>
              <Text type="secondary" style={{ fontSize: "12px" }}>
                {record.description}
              </Text>
            </Space>
          )}
        />
        <Table.Column
          dataIndex="template_id"
          title="Template"
          render={(value) => (
            <Text code style={{ fontSize: "11px" }}>
              {value.substring(0, 20)}...
            </Text>
          )}
        />
        <Table.Column
          dataIndex="status"
          title="Status"
          render={(value) => <WorkflowStatusBadge status={value} />}
        />
        <Table.Column
          dataIndex="is_deployed"
          title="Deployment"
          render={(value) => <DeploymentBadge isDeployed={value} />}
        />
        <Table.Column
          dataIndex="nifi_status"
          title="NiFi Status"
          render={(value) => (
            value ? <Tag color="blue">{value}</Tag> : <Text type="secondary">N/A</Text>
          )}
        />
        <Table.Column
          title="Actions"
          dataIndex="actions"
          render={(_, record: Workflow) => (
            <Space>
              <ShowButton hideText size="small" recordItemId={record.workflow_id} />
              <EditButton hideText size="small" recordItemId={record.workflow_id} />
              {record.is_deployed ? (
                <>
                  {record.status === "ACTIVE" ? (
                    <Button 
                      type="text" 
                      size="small" 
                      icon={<PauseCircleOutlined />} 
                      title="Pause"
                      onClick={() => handleWorkflowAction(record.workflow_id, "pause")}
                    />
                  ) : (
                    <Button 
                      type="text" 
                      size="small" 
                      icon={<PlayCircleOutlined />} 
                      title="Resume"
                      onClick={() => handleWorkflowAction(record.workflow_id, "resume")}
                    />
                  )}
                  <Button 
                    type="text" 
                    size="small" 
                    icon={<RedoOutlined />} 
                    title="Restart"
                    onClick={() => handleWorkflowAction(record.workflow_id, "restart")}
                  />
                  <Button 
                    type="text" 
                    size="small" 
                    icon={<CloudDownloadOutlined />} 
                    title="Undeploy"
                    onClick={() => handleWorkflowAction(record.workflow_id, "undeploy")}
                  />
                </>
              ) : (
                <Button 
                  type="text" 
                  size="small" 
                  icon={<CloudUploadOutlined />} 
                  title="Deploy"
                  onClick={() => handleWorkflowAction(record.workflow_id, "deploy")}
                />
              )}
              <Button 
                type="text" 
                size="small" 
                icon={<PlayCircleOutlined />} 
                title="Execute"
                onClick={() => window.location.href = `/workflows/show/${record.workflow_id}#execute`}
              />
            </Space>
          )}
        />
      </Table>
    </List>
  );
};