import React from "react";
import { Card, Tabs, Space, Typography } from "antd";
import { EditOutlined, SettingOutlined, ExperimentOutlined } from "@ant-design/icons";
import { SchemaEditorList } from "./SchemaEditorList";
import { SchemaValidationConfig } from "./SchemaValidationConfig";
import { SchemaTester } from "./SchemaTester";

const { Title } = Typography;

export const EnhancedSchemaEditor: React.FC = () => {
  const items = [
    {
      key: "editor",
      label: (
        <Space>
          <EditOutlined />
          Schema Editor
        </Space>
      ),
      children: <SchemaEditorList />,
    },
    {
      key: "configuration",
      label: (
        <Space>
          <SettingOutlined />
          Validation Configuration
        </Space>
      ),
      children: <SchemaValidationConfig />,
    },
    {
      key: "tester",
      label: (
        <Space>
          <ExperimentOutlined />
          Schema Tester
        </Space>
      ),
      children: <SchemaTester />,
    },
  ];

  return (
    <div style={{ padding: "24px" }}>
      <div style={{ marginBottom: "24px" }}>
        <Title level={2}>📋 Enhanced Schema Management</Title>
        <Typography.Paragraph>
          Comprehensive schema management with validation configuration and testing capabilities.
          Select a schema in the Schema Editor tab to configure validation settings and test functionality.
        </Typography.Paragraph>
      </div>

      <Card size="small">
        <Tabs
          defaultActiveKey="editor"
          items={items}
          size="small"
          tabBarStyle={{ marginBottom: 16 }}
        />
      </Card>
    </div>
  );
};