import React, { useEffect } from "react";
import { List, useTable } from "@refinedev/antd";
import { Table, Space, Tag, Typography, Button, Alert } from "antd";
import { IResourceComponentsProps, BaseRecord, HttpError } from "@refinedev/core";
import { EditButton, ShowButton } from "@refinedev/antd";
import { PlayCircleOutlined, PauseCircleOutlined, RedoOutlined, CloudUploadOutlined, CloudDownloadOutlined } from "@ant-design/icons";
import { WorkflowStatusBadge, DeploymentBadge } from "../../components/workflow/StatusBadges";
import { getLogger } from "../../utils";

const { Text } = Typography;
const logger = getLogger('WORKFLOW_LIST');

export const WorkflowList: React.FC<IResourceComponentsProps> = () => {
  const { tableProps, tableQueryResult } = useTable<{ workflows: any[], total: number, page: number, page_size: number }, HttpError>({
    // Add debug logging for data transformation
    queryOptions: {
      onSuccess: (data) => {
        logger.log("Raw data received from API:", data);
        if (data && typeof data === 'object' && 'data' in data) {
          logger.log("Data structure from Refine:", data.data);
          if (data.data && typeof data.data === 'object' && 'workflows' in data.data) {
            logger.log("Workflows array:", data.data.workflows);
            logger.log("Total count:", data.data.total);
          } else {
            logger.warn("Unexpected data structure - missing workflows array");
          }
        } else {
          logger.warn("Unexpected data structure - missing data property");
        }
      },
      onError: (error) => {
        logger.error("Error fetching workflows:", error);
      }
    }
  });

  // Debug logging for table props
  useEffect(() => {
    logger.log("Table props updated:", tableProps);
    if (tableProps?.dataSource) {
      logger.log("Data source type:", typeof tableProps.dataSource);
      logger.log("Data source length:", tableProps.dataSource.length);
      if (Array.isArray(tableProps.dataSource)) {
        logger.log("First item in data source:", tableProps.dataSource[0]);
      } else {
        logger.error("Data source is not an array!", tableProps.dataSource);
      }
    }
  }, [tableProps]);

  // Debug logging for query result
  useEffect(() => {
    if (tableQueryResult?.data) {
      logger.log("Query result data:", tableQueryResult.data);
    }
    if (tableQueryResult?.error) {
      logger.error("Query result error:", tableQueryResult.error);
    }
  }, [tableQueryResult]);

  // Check if we have a data structure issue
  const hasDataStructureError = tableProps?.dataSource && !Array.isArray(tableProps.dataSource);

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