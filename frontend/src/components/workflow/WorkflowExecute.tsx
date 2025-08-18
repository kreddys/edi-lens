import React from "react";
import { useShow } from "@refinedev/core";
import { GenericWorkflowExecute } from "./GenericWorkflowExecute";

interface WorkflowExecuteProps {
  workflowId: string;
}

export const WorkflowExecute: React.FC<WorkflowExecuteProps> = ({ workflowId }) => {
  // Fetch workflow data to get the template ID
  const { queryResult } = useShow({ 
    resource: "workflows",
    id: workflowId
  });
  const { data, isLoading } = queryResult;
  const record = data?.data;

  // If we have the template ID, use the generic component
  if (record?.template_id) {
    return (
      <GenericWorkflowExecute 
        workflowId={workflowId} 
        templateId={record.template_id} 
      />
    );
  }

  // Fallback to a simple loading state
  if (isLoading) {
    return (
      <div style={{ textAlign: "center", padding: "40px" }}>
        <div>Loading workflow configuration...</div>
      </div>
    );
  }

  // If we can't find the template ID, show an error
  return (
    <div style={{ padding: "24px" }}>
      <div style={{ 
        textAlign: "center", 
        padding: "40px", 
        color: "#ff4d4f",
        border: "1px solid #ff4d4f",
        borderRadius: "4px"
      }}>
        <h3>Workflow Configuration Error</h3>
        <p>Unable to load workflow template configuration.</p>
        <p>Please ensure the workflow is properly configured with a valid template.</p>
      </div>
    </div>
  );
};