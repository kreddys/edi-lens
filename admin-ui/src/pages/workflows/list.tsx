import React from "react";
import { List, useTable } from "@refinedev/antd";
import { Table, Space, Tag, Typography, Button } from "antd";
import { IResourceComponentsProps, BaseRecord } from "@refinedev/core";
import { EditButton, ShowButton } from "@refinedev/antd";
import { PlayCircleOutlined, PauseCircleOutlined, RedoOutlined, CloudUploadOutlined, CloudDownloadOutlined } from "@ant-design/icons";
import { WorkflowStatusBadge, DeploymentBadge } from "../../components/workflow/StatusBadges";

const { Text } = Typography;

export const WorkflowList: React.FC<IResourceComponentsProps> = () => {
  const { tableProps } = useTable();

  return (
    <List>
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
          render={(_, record: BaseRecord) => (
            <Space>
              <ShowButton hideText size="small" recordItemId={record.workflow_id} />
              <EditButton hideText size="small" recordItemId={record.workflow_id} />
              {record.is_deployed ? (
                <>
                  <Button 
                    type="text" 
                    size="small" 
                    icon={<PauseCircleOutlined />} 
                    title="Pause"
                  />
                  <Button 
                    type="text" 
                    size="small" 
                    icon={<RedoOutlined />} 
                    title="Restart"
                  />
                  <Button 
                    type="text" 
                    size="small" 
                    icon={<CloudDownloadOutlined />} 
                    title="Undeploy"
                  />
                </>
              ) : (
                <Button 
                  type="text" 
                  size="small" 
                  icon={<CloudUploadOutlined />} 
                  title="Deploy"
                />
              )}
              <Button 
                type="text" 
                size="small" 
                icon={<PlayCircleOutlined />} 
                title="Execute"
              />
            </Space>
          )}
        />
      </Table>
    </List>
  );
};