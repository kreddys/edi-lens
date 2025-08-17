import React from "react";
import { Button, Space, notification } from "antd";
import {
  CloudUploadOutlined,
  CloudDownloadOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  RedoOutlined
} from "@ant-design/icons";

interface WorkflowControlProps {
  workflowId: string;
  isDeployed: boolean;
  status: string;
  onActionComplete: () => void;
}

export const WorkflowControl: React.FC<WorkflowControlProps> = ({
  workflowId,
  isDeployed,
  status,
  onActionComplete
}) => {
  const handleAction = async (action: string) => {
    try {
      // Determine the API endpoint based on the action
      let endpoint = "";
      switch (action) {
        case "deploy":
          endpoint = `/api/v1/workflows/${workflowId}/deploy`;
          break;
        case "undeploy":
          endpoint = `/api/v1/workflows/${workflowId}/undeploy`;
          break;
        case "start":
          endpoint = `/api/v1/workflows/${workflowId}/start`;
          break;
        case "stop":
          endpoint = `/api/v1/workflows/${workflowId}/stop`;
          break;
        case "restart":
          endpoint = `/api/v1/workflows/${workflowId}/restart`;
          break;
        default:
          throw new Error("Invalid action");
      }

      // Make the API call
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${localStorage.getItem("auth_token")}` // Adjust as needed
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
        start: "started",
        stop: "stopped",
        restart: "restarted"
      };

      notification.success({
        message: "Success",
        description: `Workflow successfully ${actionLabels[action]}`
      });

      // Notify parent component that action is complete
      onActionComplete();
    } catch (error: any) {
      notification.error({
        message: "Action Failed",
        description: error.message || "An error occurred while performing the action"
      });
      console.error(`${action} error:`, error);
    }
  };

  return (
    <Space>
      {isDeployed ? (
        <>
          {status === "ACTIVE" ? (
            <Button 
              type="primary" 
              icon={<PauseCircleOutlined />} 
              onClick={() => handleAction("stop")}
              danger
            >
              Pause
            </Button>
          ) : (
            <Button 
              type="primary" 
              icon={<PlayCircleOutlined />} 
              onClick={() => handleAction("start")}
            >
              Resume
            </Button>
          )}
          <Button 
            icon={<RedoOutlined />} 
            onClick={() => handleAction("restart")}
          >
            Restart
          </Button>
          <Button 
            icon={<CloudDownloadOutlined />} 
            onClick={() => handleAction("undeploy")}
            danger
          >
            Undeploy
          </Button>
        </>
      ) : (
        <Button 
          type="primary" 
          icon={<CloudUploadOutlined />} 
          onClick={() => handleAction("deploy")}
        >
          Deploy
        </Button>
      )}
    </Space>
  );
};