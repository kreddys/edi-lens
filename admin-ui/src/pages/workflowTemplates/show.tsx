import React from "react";
import {
  Show,
  NumberField,
  TagField,
} from "@refinedev/antd";
import {
  Card,
  Row,
  Col,
  Typography,
  Tag,
  Space,
  Divider,
  Descriptions,
  Spin,
  Alert,
  Button
} from "antd";
import { IResourceComponentsProps, useShow, useDataProvider } from "@refinedev/core";
import { TemplateStatusBadge } from "../../components/workflow/StatusBadges";

const { Text, Title } = Typography;

export const WorkflowTemplateShow: React.FC<IResourceComponentsProps> = () => {
  const { queryResult } = useShow();
  const { data, isLoading } = queryResult;
  const record = data?.data;

  const dataProvider = useDataProvider();

  if (isLoading) {
    return (
      <div style={{ textAlign: "center", padding: "40px" }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>
          <Text>Loading template details...</Text>
        </div>
      </div>
    );
  }

  return (
    <Show isLoading={isLoading}>
      <Row gutter={[24, 24]}>
        <Col xs={24} lg={16}>
          <Card title="Template Information" size="small">
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="Name">
                <Text strong>{record?.name}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Status">
                <TemplateStatusBadge status={record?.status} />
              </Descriptions.Item>
              <Descriptions.Item label="Description" span={2}>
                <Text>{record?.description || "No description provided"}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Category">
                <Tag>{record?.category}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Scope">
                <Tag>{record?.scope}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Version">
                <Tag>{record?.version}</Tag>
              </Descriptions.Item>
              {record?.tags && record.tags.length > 0 && (
                <Descriptions.Item label="Tags" span={2}>
                  <Space>
                    {record.tags.map((tag: string) => (
                      <Tag key={tag}>{tag}</Tag>
                    ))}
                  </Space>
                </Descriptions.Item>
              )}
              {record?.features && record.features.length > 0 && (
                <Descriptions.Item label="Features" span={2}>
                  <Space>
                    {record.features.map((feature: string) => (
                      <Tag key={feature}>{feature}</Tag>
                    ))}
                  </Space>
                </Descriptions.Item>
              )}
            </Descriptions>
          </Card>

          <Card title="Documentation" size="small" style={{ marginTop: 16 }}>
            {record?.documentation ? (
              <div style={{ whiteSpace: "pre-wrap" }}>
                {record.documentation}
              </div>
            ) : (
              <Text type="secondary">No documentation available</Text>
            )}
          </Card>

          {record?.ui_configuration && (
            <Card title="UI Configuration" size="small" style={{ marginTop: 16 }}>
              <pre style={{ 
                background: "#f5f5f5", 
                padding: 16, 
                borderRadius: 4,
                fontSize: 12,
                overflowX: "auto",
                maxHeight: 300
              }}>
                {JSON.stringify(record.ui_configuration, null, 2)}
              </pre>
            </Card>
          )}
        </Col>

        <Col xs={24} lg={8}>
          <Card title="Template Details" size="small">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Template ID">
                <Text code>{record?.template_id}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Maintainer">
                <Text>{record?.maintainer}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Usage Count">
                <Text>{record?.usage_count}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Created">
                <Text>{new Date(record?.created_at).toLocaleString()}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Updated">
                <Text>{new Date(record?.updated_at).toLocaleString()}</Text>
              </Descriptions.Item>
              {record?.based_on && (
                <Descriptions.Item label="Based On">
                  <Text code>{record.based_on}</Text>
                </Descriptions.Item>
              )}
            </Descriptions>
          </Card>

          <Card title="Processing Capabilities" size="small" style={{ marginTop: 16 }}>
            {record?.processing_capabilities && record.processing_capabilities.length > 0 ? (
              <Space wrap>
                {record.processing_capabilities.map((capability: string) => (
                  <Tag key={capability}>{capability}</Tag>
                ))}
              </Space>
            ) : (
              <Text type="secondary">No processing capabilities specified</Text>
            )}
          </Card>

          <Card title="Supported File Types" size="small" style={{ marginTop: 16 }}>
            {record?.supported_file_types && record.supported_file_types.length > 0 ? (
              <Space wrap>
                {record.supported_file_types.map((fileType: string) => (
                  <Tag key={fileType}>{fileType}</Tag>
                ))}
              </Space>
            ) : (
              <Text type="secondary">No file types specified</Text>
            )}
          </Card>

          <Card title="Use Cases" size="small" style={{ marginTop: 16 }}>
            {record?.use_cases && record.use_cases.length > 0 ? (
              <Space wrap>
                {record.use_cases.map((useCase: string) => (
                  <Tag key={useCase}>{useCase}</Tag>
                ))}
              </Space>
            ) : (
              <Text type="secondary">No use cases specified</Text>
            )}
          </Card>

          <Card title="Industry Tags" size="small" style={{ marginTop: 16 }}>
            {record?.industry_tags && record.industry_tags.length > 0 ? (
              <Space wrap>
                {record.industry_tags.map((industryTag: string) => (
                  <Tag key={industryTag}>{industryTag}</Tag>
                ))}
              </Space>
            ) : (
              <Text type="secondary">No industry tags specified</Text>
            )}
          </Card>
        </Col>
      </Row>
    </Show>
  );
};