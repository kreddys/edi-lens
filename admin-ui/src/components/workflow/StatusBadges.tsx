import React from "react";
import { Tag } from "antd";

// Status badges for templates
export const TemplateStatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const statusConfig: Record<string, { color: string; text: string }> = {
    ACTIVE: { color: "success", text: "Active" },
    DEPRECATED: { color: "warning", text: "Deprecated" },
    ARCHIVED: { color: "default", text: "Archived" },
  };
  
  const config = statusConfig[status] || { color: "default", text: status };
  return <Tag color={config.color}>{config.text}</Tag>;
};

// Scope badges for templates
export const ScopeBadge: React.FC<{ scope: string }> = ({ scope }) => {
  const scopeConfig: Record<string, { color: string; text: string }> = {
    GLOBAL: { color: "blue", text: "Global" },
    TENANT: { color: "green", text: "Tenant" },
  };
  
  const config = scopeConfig[scope] || { color: "default", text: scope };
  return <Tag color={config.color}>{config.text}</Tag>;
};

// Category badges for templates
export const CategoryBadge: React.FC<{ category: string }> = ({ category }) => {
  const categoryConfig: Record<string, { color: string; text: string }> = {
    BATCH: { color: "purple", text: "Batch" },
    REALTIME: { color: "cyan", text: "Real-time" },
    TRANSFORMATION: { color: "orange", text: "Transformation" },
    INTEGRATION: { color: "geekblue", text: "Integration" },
  };
  
  const config = categoryConfig[category] || { color: "default", text: category };
  return <Tag color={config.color}>{config.text}</Tag>;
};

// Status badges for workflows
export const WorkflowStatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const statusConfig: Record<string, { color: string; text: string }> = {
    ACTIVE: { color: "success", text: "Active" },
    PAUSED: { color: "warning", text: "Paused" },
    ERROR: { color: "error", text: "Error" },
    DELETED: { color: "default", text: "Deleted" },
  };
  
  const config = statusConfig[status] || { color: "default", text: status };
  return <Tag color={config.color}>{config.text}</Tag>;
};

// Deployment status badges
export const DeploymentBadge: React.FC<{ isDeployed: boolean }> = ({ isDeployed }) => {
  if (isDeployed) {
    return <Tag color="green">Deployed</Tag>;
  }
  return <Tag color="default">Not Deployed</Tag>;
};