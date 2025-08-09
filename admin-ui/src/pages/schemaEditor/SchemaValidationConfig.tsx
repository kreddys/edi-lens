import React, { useState, useEffect } from "react";
import {
  Card,
  Form,
  Select,
  Switch,
  Button,
  Space,
  Typography,
  Alert,
  Divider,
  Descriptions,
  Tag,
  notification,
  Row,
  Col,
  Input,
  Tooltip
} from "antd";
import {
  SaveOutlined,
  SettingOutlined,
  InfoCircleOutlined,
  ExperimentOutlined,
  EditOutlined
} from "@ant-design/icons";
import { useCustom, useCreate, useUpdate } from "@refinedev/core";

const { Text } = Typography;
const { TextArea } = Input;

interface ValidationConfig {
  id?: number;
  schema_name: string;
  snip_level: "SNIP1" | "SNIP2" | "SNIP3" | "SNIP4" | "SNIP5";
  generate_ta1: boolean;
  generate_999: boolean;
  custom_validation_rules?: string; // JSON string
}

interface SchemaValidationConfigProps {
  selectedSchema?: string;
}

export const SchemaValidationConfig: React.FC<SchemaValidationConfigProps> = ({
  selectedSchema
}) => {
  const [form] = Form.useForm();
  const [config, setConfig] = useState<ValidationConfig | null>(null);
  const [isEditing, setIsEditing] = useState(false);

  // Fetch existing configuration for the selected schema
  const { data: configData, refetch: refetchConfig } = useCustom<ValidationConfig>({
    url: `/schema-validation-config/${selectedSchema}`,
    method: "get",
    queryOptions: {
      enabled: !!selectedSchema,
    },
  });

  const { mutate: createConfig } = useCreate();
  const { mutate: updateConfig } = useUpdate();

  useEffect(() => {
    if (configData?.data) {
      setConfig(configData.data);
      form.setFieldsValue({
        ...configData.data,
        custom_validation_rules: configData.data.custom_validation_rules 
          ? JSON.stringify(JSON.parse(configData.data.custom_validation_rules), null, 2)
          : ""
      });
    } else if (selectedSchema) {
      // Set default values for new schema
      const defaultConfig: Omit<ValidationConfig, 'id'> = {
        schema_name: selectedSchema,
        snip_level: "SNIP3",
        generate_ta1: true,
        generate_999: false,
        custom_validation_rules: ""
      };
      form.setFieldsValue(defaultConfig);
      setConfig(null);
    }
  }, [configData, selectedSchema, form]);

  const saveConfiguration = async (values: ValidationConfig) => {
    if (!selectedSchema) return;

    try {
      // Parse custom validation rules if provided
      let parsedRules = null;
      if (values.custom_validation_rules?.trim()) {
        try {
          parsedRules = JSON.parse(values.custom_validation_rules);
        } catch (e) {
          notification.error({
            message: "Invalid JSON",
            description: "Custom validation rules must be valid JSON"
          });
          return;
        }
      }

      const payload = {
        ...values,
        schema_name: selectedSchema,
        custom_validation_rules: parsedRules ? JSON.stringify(parsedRules) : null
      };

      if (config?.id) {
        updateConfig({
          resource: "schema-validation-config",
          id: config.id,
          values: payload,
        }, {
          onSuccess: () => {
            notification.success({
              message: "Configuration Updated",
              description: "Schema validation configuration has been updated successfully"
            });
            setIsEditing(false);
            refetchConfig();
          }
        });
      } else {
        createConfig({
          resource: "schema-validation-config",
          values: payload,
        }, {
          onSuccess: () => {
            notification.success({
              message: "Configuration Saved",
              description: "Schema validation configuration has been saved successfully"
            });
            setIsEditing(false);
            refetchConfig();
          }
        });
      }
    } catch (error) {
      notification.error({
        message: "Save Failed",
        description: "Failed to save schema validation configuration"
      });
    }
  };

  const testSchemaConfiguration = () => {
    notification.info({
      message: "Test Configuration",
      description: "Navigate to EDI Inspector to test this schema configuration with EDI content"
    });
  };

  if (!selectedSchema) {
    return (
      <Card size="small">
        <div style={{ textAlign: "center", padding: "40px", color: "#8c8c8c" }}>
          <SettingOutlined style={{ fontSize: "48px", marginBottom: "16px" }} />
          <div>
            <Text>Select a schema to configure validation settings</Text>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card 
      title={
        <Space>
          <SettingOutlined />
          <span>Validation Configuration</span>
          <Tag color="blue">{selectedSchema}</Tag>
        </Space>
      }
      size="small"
      extra={
        <Space>
          <Button
            icon={<ExperimentOutlined />}
            onClick={testSchemaConfiguration}
          >
            Test Schema
          </Button>
          {!isEditing ? (
            <Button
              type="primary"
              icon={<EditOutlined />}
              onClick={() => setIsEditing(true)}
            >
              Edit Config
            </Button>
          ) : (
            <Space>
              <Button onClick={() => setIsEditing(false)}>
                Cancel
              </Button>
              <Button
                type="primary"
                icon={<SaveOutlined />}
                onClick={() => form.submit()}
              >
                Save Config
              </Button>
            </Space>
          )}
        </Space>
      }
    >
      {!isEditing && config ? (
        // Display Mode
        <Space direction="vertical" style={{ width: "100%" }}>
          <Alert
            message="Current Configuration"
            description="This schema has validation configuration applied. Edit to modify settings."
            type="info"
            showIcon
          />
          
          <Row gutter={[16, 16]}>
            <Col xs={24} md={12}>
              <Descriptions title="Validation Settings" size="small" column={1}>
                <Descriptions.Item label="SNIP Level">
                  <Tag color="purple">{config.snip_level}</Tag>
                  <Tooltip title="Syntax and Implementation Profile Level">
                    <InfoCircleOutlined style={{ marginLeft: 4 }} />
                  </Tooltip>
                </Descriptions.Item>
                <Descriptions.Item label="TA1 Generation">
                  <Tag color={config.generate_ta1 ? "success" : "default"}>
                    {config.generate_ta1 ? "Enabled" : "Disabled"}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="999 Generation">
                  <Tag color={config.generate_999 ? "success" : "default"}>
                    {config.generate_999 ? "Enabled" : "Disabled"}
                  </Tag>
                </Descriptions.Item>
              </Descriptions>
            </Col>
            <Col xs={24} md={12}>
              <Descriptions title="Usage Statistics" size="small" column={1}>
                <Descriptions.Item label="Validations This Month">
                  <Text strong>156</Text>
                </Descriptions.Item>
                <Descriptions.Item label="Avg Processing Time">
                  <Text>189ms</Text>
                </Descriptions.Item>
                <Descriptions.Item label="Success Rate">
                  <Text style={{ color: "#52c41a" }}>95.2%</Text>
                </Descriptions.Item>
              </Descriptions>
            </Col>
          </Row>

          {config.custom_validation_rules && (
            <>
              <Divider />
              <div>
                <Text strong>Custom Validation Rules:</Text>
                <TextArea
                  value={JSON.stringify(JSON.parse(config.custom_validation_rules), null, 2)}
                  readOnly
                  rows={4}
                  style={{ marginTop: 8, fontFamily: "monospace", fontSize: "12px" }}
                />
              </div>
            </>
          )}
        </Space>
      ) : (
        // Edit Mode
        <Form
          form={form}
          layout="vertical"
          onFinish={saveConfiguration}
        >
          <Alert
            message="Schema Validation Configuration"
            description="Configure validation settings that will be applied when this schema is used for EDI validation."
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />

          <Row gutter={[16, 16]}>
            <Col xs={24} md={8}>
              <Form.Item
                label={
                  <Space>
                    <span>SNIP Level</span>
                    <Tooltip title="Syntax and Implementation Profile - higher levels enforce stricter validation">
                      <InfoCircleOutlined />
                    </Tooltip>
                  </Space>
                }
                name="snip_level"
                rules={[{ required: true, message: "Please select a SNIP level" }]}
              >
                <Select>
                  <Select.Option value="SNIP1">SNIP1 - Basic Syntax</Select.Option>
                  <Select.Option value="SNIP2">SNIP2 - Enhanced Syntax</Select.Option>
                  <Select.Option value="SNIP3">SNIP3 - Standard Validation</Select.Option>
                  <Select.Option value="SNIP4">SNIP4 - Strict Validation</Select.Option>
                  <Select.Option value="SNIP5">SNIP5 - Maximum Validation</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            
            <Col xs={24} md={8}>
              <Form.Item
                label={
                  <Space>
                    <span>Generate TA1</span>
                    <Tooltip title="Generate TA1 Interchange Acknowledgment">
                      <InfoCircleOutlined />
                    </Tooltip>
                  </Space>
                }
                name="generate_ta1"
                valuePropName="checked"
              >
                <Switch checkedChildren="Enabled" unCheckedChildren="Disabled" />
              </Form.Item>
            </Col>
            
            <Col xs={24} md={8}>
              <Form.Item
                label={
                  <Space>
                    <span>Generate 999</span>
                    <Tooltip title="Generate 999 Functional Acknowledgment">
                      <InfoCircleOutlined />
                    </Tooltip>
                  </Space>
                }
                name="generate_999"
                valuePropName="checked"
              >
                <Switch checkedChildren="Enabled" unCheckedChildren="Disabled" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            label={
              <Space>
                <span>Custom Validation Rules (Optional)</span>
                <Tooltip title="Advanced JSON configuration for custom business rules">
                  <InfoCircleOutlined />
                </Tooltip>
              </Space>
            }
            name="custom_validation_rules"
          >
            <TextArea
              placeholder={`{
  "business_rules": {
    "required_loops": ["2000A", "2300"],
    "max_occurrences": {
      "CLM": 1,
      "SBR": 5
    }
  }
}`}
              rows={6}
              style={{ fontFamily: "monospace", fontSize: "12px" }}
            />
          </Form.Item>

          <Alert
            message="Configuration Impact"
            description={
              <ul style={{ margin: 0, paddingLeft: 16 }}>
                <li>These settings apply to all validations using this schema</li>
                <li>Changes affect both API and SFTP validation processing</li>
                <li>Custom rules are applied in addition to standard SNIP validation</li>
              </ul>
            }
            type="warning"
            showIcon
            style={{ marginTop: 16 }}
          />
        </Form>
      )}
    </Card>
  );
};