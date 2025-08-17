import React, { useEffect } from "react";
import { List, useTable } from "@refinedev/antd";
import { Table, Space, Tag, Typography, Alert } from "antd";
import { IResourceComponentsProps, BaseRecord, HttpError } from "@refinedev/core";
import { EditButton, ShowButton } from "@refinedev/antd";
import { TemplateStatusBadge, ScopeBadge, CategoryBadge } from "../../components/workflow/StatusBadges";
import { getLogger } from "../../utils";

const { Text } = Typography;
const logger = getLogger('TEMPLATES_LIST');

export const WorkflowTemplateList: React.FC<IResourceComponentsProps> = () => {
  const { tableProps, tableQueryResult } = useTable<{ templates: any[], total: number, page: number, page_size: number }, HttpError>({
    // Add debug logging for data transformation
    queryOptions: {
      onSuccess: (data) => {
        logger.log("Raw data received from API:", data);
        if (data && typeof data === 'object' && 'data' in data) {
          logger.log("Data structure from Refine:", data.data);
          logger.log("Data type:", typeof data.data);
          if (Array.isArray(data.data)) {
            logger.log("Templates array length:", data.data.length);
            if (data.data.length > 0) {
              logger.log("First template:", data.data[0]);
            }
          } else if (data.data && typeof data.data === 'object' && 'templates' in data.data) {
            logger.log("Templates array:", data.data.templates);
            logger.log("Total count:", data.data.total);
          } else {
            logger.warn("Unexpected data structure - unknown format");
            logger.log("Data content:", data.data);
          }
        } else {
          logger.warn("Unexpected data structure - missing data property");
        }
      },
      onError: (error) => {
        logger.error("Error fetching templates:", error);
      }
    }
  });

  // Debug logging for table props
  useEffect(() => {
    logger.log("Table props updated:", tableProps);
    if (tableProps?.dataSource) {
      logger.log("Data source type:", typeof tableProps.dataSource);
      if (Array.isArray(tableProps.dataSource)) {
        logger.log("Data source length:", tableProps.dataSource.length);
        if (tableProps.dataSource.length > 0) {
          logger.log("First item in data source:", tableProps.dataSource[0]);
        }
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
      <Table {...tableProps} rowKey="template_id">
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
          dataIndex="category"
          title="Category"
          render={(value) => <CategoryBadge category={value} />}
        />
        <Table.Column
          dataIndex="scope"
          title="Scope"
          render={(value) => <ScopeBadge scope={value} />}
        />
        <Table.Column
          dataIndex="status"
          title="Status"
          render={(value) => <TemplateStatusBadge status={value} />}
        />
        <Table.Column
          dataIndex="version"
          title="Version"
          render={(value) => <Tag>{value}</Tag>}
        />
        <Table.Column
          dataIndex="usage_count"
          title="Usage"
          render={(value) => <Text type="secondary">{value} workflows</Text>}
        />
        <Table.Column
          title="Actions"
          dataIndex="actions"
          render={(_, record: BaseRecord) => (
            <Space>
              <ShowButton hideText size="small" recordItemId={record.template_id} />
              <EditButton hideText size="small" recordItemId={record.template_id} />
            </Space>
          )}
        />
      </Table>
    </List>
  );
};