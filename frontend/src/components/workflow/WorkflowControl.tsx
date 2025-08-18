import React from "react";
import { Button, Space, App } from "antd";
import {
  CloudUploadOutlined,
  CloudDownloadOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  RedoOutlined
} from "@ant-design/icons";
import { useDataProvider } from "@refinedev/core";

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
  const { notification } = App.useApp();
  
  const dataProvider = useDataProvider();

  const handleAction = async (action: string) => {
    try {
      // Determine the API endpoint based on the action
      let endpoint = "";
      switch (action) {
        case "deploy":
          endpoint = `/workflows/${workflowId}/deploy`;
          break;
        case "undeploy":
          endpoint = `/workflows/${workflowId}/undeploy`;
          break;
        case "start":
        case "resume":
          endpoint = `/workflows/${workflowId}/resume`;
          break;
        case "stop":
        case "pause":
          endpoint = `/workflows/${workflowId}/pause`;
          break;
        case "restart":
          endpoint = `/workflows/${workflowId}/restart`;
          break;
        default:
          throw new Error("Invalid action");
      }

      // Make the API call using data provider
      await dataProvider().custom!({
        url: endpoint,
        method: "post"
      });

      // Show success notification
      const actionLabels: Record<string, string> = {
        deploy: "deployed",
        undeploy: "undeployed",
        start: "started",
        stop: "stopped",
        pause: "paused",
        resume: "resumed",
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
              onClick={() => handleAction("pause")}
              danger
            >
              Pause
            </Button>
          ) : (
            <Button 
              type="primary" 
              icon={<PlayCircleOutlined />} 
              onClick={() => handleAction("resume")}
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