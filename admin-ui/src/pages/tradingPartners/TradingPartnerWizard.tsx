import React, { useState } from "react";
import {
  Steps,
  Card,
  Form,
  Input,
  Button,
  Space,
  Typography,
  Select,
  Switch,
  Divider,
  Row,
  Col,
  Alert,
  notification,
  Tag,
  Table,
  Modal,
  Checkbox
} from "antd";
import {
  UserOutlined,
  SettingOutlined,
  CloudServerOutlined,
  SaveOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined
} from "@ant-design/icons";
import { useCreate, useUpdate, useCustom } from "@refinedev/core";
import { useSftpConfiguration } from "../../hooks/useSftpConfiguration";

const { Title, Text } = Typography;
const { TextArea } = Input;

interface Profile {
  id?: number;
  name: string;
  validation_schema_name?: string;
  snip_level: "SNIP1" | "SNIP2" | "SNIP3" | "SNIP4" | "SNIP5";
  generate_ta1: boolean;
  generate_999: boolean;
  criteria: ProfileCriterion[];
}

interface ProfileCriterion {
  field_source: "ISA" | "GS" | "FILENAME";
  field_identifier: string;
  operator: "EQUALS" | "STARTS_WITH" | "CONTAINS";
  value: string;
}

interface SFTPConfig {
  enabled: boolean;
  username?: string;
  authentication_type?: "PASSWORD" | "SSH_KEY" | "BOTH";
  password?: string;
  ssh_public_key?: string;
  file_patterns?: string[];
}

export interface TradingPartnerData {
  id?: number;
  name: string;
  description?: string;
  integration_methods: string[];
  profiles: Profile[];
  sftp_config?: SFTPConfig;
}

interface TradingPartnerWizardProps {
  initialData?: TradingPartnerData;
  mode: "create" | "edit";
  onSuccess?: () => void;
  onCancel?: () => void;
}

export const TradingPartnerWizard: React.FC<TradingPartnerWizardProps> = ({
  initialData,
  mode,
  onSuccess,
  onCancel
}) => {
  const [currentStep, setCurrentStep] = useState(0);
  const [form] = Form.useForm();
  const [partnerData, setPartnerData] = useState<TradingPartnerData>(
    initialData || {
      name: "",
      description: "",
      integration_methods: ["SFTP"],
      profiles: []
    }
  );
  const [profileModalVisible, setProfileModalVisible] = useState(false);
  const [editingProfile, setEditingProfile] = useState<Profile | null>(null);
  const [profileForm] = Form.useForm();

  const { mutate: createPartner } = useCreate();
  const { mutate: updatePartner } = useUpdate();
  const { createSftpConfiguration } = useSftpConfiguration(partnerData.id);

  // Fetch available schemas
  const { data: schemasData } = useCustom({
    url: "/schemas",
    method: "get",
  });

  const schemas = schemasData?.data?.base_schemas || [];
  const specializedSchemas = schemasData?.data?.specialized_schemas || [];
  const allSchemas = [...schemas, ...specializedSchemas];

  const steps = [
    {
      title: "Basic Info",
      icon: <UserOutlined />,
      description: "Partner details and integration method"
    },
    {
      title: "Profiles",
      icon: <SettingOutlined />,
      description: "Configure validation profiles"
    },
    {
      title: "Integration",
      icon: <CloudServerOutlined />,
      description: "SFTP/API configuration"
    }
  ];

  const handleNext = async () => {
    try {
      if (currentStep === 0) {
        const values = await form.validateFields();
        setPartnerData(prev => ({ ...prev, ...values }));
      }
      setCurrentStep(prev => prev + 1);
    } catch (error) {
      console.error("Validation failed:", error);
    }
  };

  const handlePrev = () => {
    setCurrentStep(prev => prev - 1);
  };

  const handleFinish = async () => {
    try {
      if (currentStep === 2) {
        const integrationValues = await form.validateFields();
        const finalData = { ...partnerData, ...integrationValues };

        if (mode === "create") {
          createPartner({
            resource: "trading-partners",
            values: finalData,
          }, {
            onSuccess: async (data) => {
              // If SFTP is enabled, create SFTP configuration
              if (partnerData.integration_methods.includes("SFTP") && integrationValues.sftp_config) {
                try {
                  await createSftpConfiguration({
                    partner_id: data.data.id as number,
                    sftp_enabled: true,
                    sftp_username: integrationValues.sftp_config.username,
                    authentication_type: integrationValues.sftp_config.authentication_type || "PASSWORD",
                    password: integrationValues.sftp_config.password,
                    ssh_public_key: integrationValues.sftp_config.ssh_public_key,
                    file_name_patterns: integrationValues.sftp_config.file_patterns ? JSON.stringify(integrationValues.sftp_config.file_patterns) : undefined,
                  });
                } catch (sftpError) {
                  console.error("Failed to create SFTP configuration:", sftpError);
                  notification.warning({
                    message: "Partner Created, SFTP Setup Failed",
                    description: "Trading partner was created but SFTP configuration failed. Please set up SFTP manually."
                  });
                }
              }
              
              notification.success({
                message: "Success",
                description: "Trading partner created successfully"
              });
              onSuccess?.();
            }
          });
        } else {
          updatePartner({
            resource: "trading-partners",
            id: finalData.id as number,
            values: finalData,
          }, {
            onSuccess: () => {
              notification.success({
                message: "Success",
                description: "Trading partner updated successfully"
              });
              onSuccess?.();
            }
          });
        }
      }
    } catch (error) {
      console.error("Failed to save:", error);
    }
  };

  const addProfile = () => {
    setEditingProfile(null);
    profileForm.resetFields();
    profileForm.setFieldsValue({
      snip_level: "SNIP3",
      generate_ta1: true,
      generate_999: false,
      criteria: []
    });
    setProfileModalVisible(true);
  };

  const editProfile = (profile: Profile, index: number) => {
    setEditingProfile({ ...profile, id: index });
    profileForm.setFieldsValue(profile);
    setProfileModalVisible(true);
  };

  const saveProfile = async () => {
    try {
      const values = await profileForm.validateFields();
      const newProfile: Profile = {
        ...values,
        criteria: values.criteria || []
      };

      if (editingProfile?.id !== undefined) {
        // Edit existing profile
        const updatedProfiles = [...partnerData.profiles];
        updatedProfiles[editingProfile.id] = newProfile;
        setPartnerData(prev => ({ ...prev, profiles: updatedProfiles }));
      } else {
        // Add new profile
        setPartnerData(prev => ({
          ...prev,
          profiles: [...prev.profiles, newProfile]
        }));
      }

      setProfileModalVisible(false);
      notification.success({
        message: "Profile Saved",
        description: "Profile configuration has been saved"
      });
    } catch (error) {
      console.error("Profile validation failed:", error);
    }
  };

  const deleteProfile = (index: number) => {
    const updatedProfiles = partnerData.profiles.filter((_, i) => i !== index);
    setPartnerData(prev => ({ ...prev, profiles: updatedProfiles }));
    notification.success({
      message: "Profile Deleted",
      description: "Profile has been removed"
    });
  };

  const renderBasicInfo = () => (
    <Card title="Trading Partner Information">
      <Form form={form} layout="vertical" initialValues={partnerData}>
        <Row gutter={[16, 16]}>
          <Col xs={24} md={12}>
            <Form.Item
              label="Partner Name"
              name="name"
              rules={[{ required: true, message: "Please enter partner name" }]}
            >
              <Input placeholder="Enter trading partner name" />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item
              label="Integration Methods"
              name="integration_methods"
              rules={[{ required: true, message: "Please select at least one integration method" }]}
            >
              <Checkbox.Group>
                <Space direction="vertical">
                  <Checkbox value="SFTP">SFTP Integration</Checkbox>
                  <Checkbox value="API">API Integration</Checkbox>
                </Space>
              </Checkbox.Group>
            </Form.Item>
          </Col>
          <Col xs={24}>
            <Form.Item label="Description" name="description">
              <TextArea
                rows={3}
                placeholder="Optional description of the trading partner"
              />
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </Card>
  );

  const renderProfiles = () => (
    <Card 
      title="Validation Profiles"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={addProfile}>
          Add Profile
        </Button>
      }
    >
      <Alert
        message="Profile Configuration"
        description="Each profile defines validation rules, schema selection, and processing settings for different types of EDI documents."
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      {partnerData.profiles.length === 0 ? (
        <div style={{ textAlign: "center", padding: "40px", color: "#8c8c8c" }}>
          <SettingOutlined style={{ fontSize: "48px", marginBottom: "16px" }} />
          <div>
            <Text>No profiles configured. Click "Add Profile" to create your first validation profile.</Text>
          </div>
        </div>
      ) : (
        <Table
          dataSource={partnerData.profiles.map((profile, index) => ({ ...profile, key: index }))}
          pagination={false}
          size="small"
        >
          <Table.Column
            title="Profile Name"
            dataIndex="name"
            render={(name, record: any) => (
              <div>
                <Text strong>{name}</Text>
                <br />
                <Text type="secondary" style={{ fontSize: "12px" }}>
                  Schema: {record.validation_schema_name || "Auto-detect"}
                </Text>
              </div>
            )}
          />
          <Table.Column
            title="Schema"
            dataIndex="validation_schema_name"
            render={(schema) => (
              <Text code style={{ fontSize: "11px" }}>
                {schema || "Auto-detect"}
              </Text>
            )}
          />
          <Table.Column
            title="SNIP Level"
            dataIndex="snip_level"
            render={(level) => <Tag color="purple">{level}</Tag>}
          />
          <Table.Column
            title="TA1/999"
            render={(_, record: any) => (
              <Space>
                <Tag color={record.generate_ta1 ? "success" : "default"}>
                  TA1: {record.generate_ta1 ? "ON" : "OFF"}
                </Tag>
                <Tag color={record.generate_999 ? "success" : "default"}>
                  999: {record.generate_999 ? "ON" : "OFF"}
                </Tag>
              </Space>
            )}
          />
          <Table.Column
            title="Actions"
            render={(_, record: any, index: number) => (
              <Space>
                <Button
                  type="text"
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => editProfile(record, index)}
                />
                <Button
                  type="text"
                  size="small"
                  icon={<DeleteOutlined />}
                  danger
                  onClick={() => deleteProfile(index)}
                />
              </Space>
            )}
          />
        </Table>
      )}
    </Card>
  );

  const renderIntegration = () => (
    <Card title="Integration Configuration">
      <Form form={form} layout="vertical" initialValues={partnerData}>
        {partnerData.integration_methods.includes("SFTP") && (
          <>
            <Alert
              message="Managed SFTP Configuration"
              description="SFTP access will be automatically configured on our managed server. You'll receive connection details after partner creation."
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />
            
            <Row gutter={[16, 16]}>
              <Col xs={24} md={12}>
                <Form.Item
                  label="SFTP Username"
                  name={["sftp_config", "username"]}
                  rules={[{ required: partnerData.integration_methods.includes("SFTP") }]}
                  help="Username for SFTP access (will be prefixed with tenant ID)"
                >
                  <Input placeholder="e.g., partner_claims" />
                </Form.Item>
              </Col>
              <Col xs={24} md={12}>
                <Form.Item
                  label="Authentication Type"
                  name={["sftp_config", "authentication_type"]}
                  initialValue="PASSWORD"
                >
                  <Select>
                    <Select.Option value="PASSWORD">Password Only</Select.Option>
                    <Select.Option value="SSH_KEY">SSH Key Only</Select.Option>
                    <Select.Option value="BOTH">Password + SSH Key</Select.Option>
                  </Select>
                </Form.Item>
              </Col>
              <Col xs={24} md={12}>
                <Form.Item
                  label="Password"
                  name={["sftp_config", "password"]}
                  rules={[{ required: partnerData.integration_methods.includes("SFTP") }]}
                  help="Minimum 8 characters"
                >
                  <Input.Password placeholder="Enter secure password" />
                </Form.Item>
              </Col>
              <Col xs={24} md={12}>
                <Form.Item
                  label="SSH Public Key (Optional)"
                  name={["sftp_config", "ssh_public_key"]}
                  help="For key-based authentication"
                >
                  <TextArea
                    rows={3}
                    placeholder="ssh-rsa AAAAB3NzaC1yc2EAAAA..."
                  />
                </Form.Item>
              </Col>
              <Col xs={24}>
                <Form.Item
                  label="File Patterns (Optional)"
                  name={["sftp_config", "file_patterns"]}
                  help="File patterns for profile matching (e.g., claims_*.edi, eligibility_*.x12)"
                >
                  <Select
                    mode="tags"
                    placeholder="claims_*.edi, eligibility_*.x12"
                    tokenSeparators={[","]}
                  />
                </Form.Item>
              </Col>
            </Row>
          </>
        )}

        {partnerData.integration_methods.includes("API") && (
          <>
            <Divider />
            <Alert
              message="API Configuration"
              description="API integration uses the standard /api/v1/validate endpoint with JWT authentication"
              type="info"
              showIcon
            />
            <Text style={{ color: "#666", marginTop: 8, display: "block" }}>
              No additional configuration required. Partners can use the validation API with proper authentication tokens.
            </Text>
          </>
        )}
      </Form>
    </Card>
  );

  return (
    <div style={{ padding: "24px" }}>
      <Title level={2}>
        {mode === "create" ? "Create Trading Partner" : "Edit Trading Partner"}
      </Title>

      <Steps current={currentStep} items={steps} style={{ marginBottom: "24px" }} />

      <div style={{ marginBottom: "24px" }}>
        {currentStep === 0 && renderBasicInfo()}
        {currentStep === 1 && renderProfiles()}
        {currentStep === 2 && renderIntegration()}
      </div>

      <div style={{ textAlign: "right" }}>
        <Space>
          {onCancel && (
            <Button onClick={onCancel}>Cancel</Button>
          )}
          {currentStep > 0 && (
            <Button onClick={handlePrev}>Previous</Button>
          )}
          {currentStep < steps.length - 1 && (
            <Button type="primary" onClick={handleNext}>
              Next
            </Button>
          )}
          {currentStep === steps.length - 1 && (
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={handleFinish}
            >
              {mode === "create" ? "Create Partner" : "Update Partner"}
            </Button>
          )}
        </Space>
      </div>

      {/* Profile Configuration Modal */}
      <Modal
        title={editingProfile ? "Edit Profile" : "Add Profile"}
        open={profileModalVisible}
        onCancel={() => setProfileModalVisible(false)}
        onOk={saveProfile}
        width={700}
        destroyOnClose
      >
        <Form form={profileForm} layout="vertical">
          <Row gutter={[16, 16]}>
            <Col xs={24} md={12}>
              <Form.Item
                label="Profile Name"
                name="name"
                rules={[{ required: true }]}
              >
                <Input placeholder="e.g., Healthcare Claims Standard" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                label="Validation Schema"
                name="validation_schema_name"
                help="Leave empty for auto-detection"
              >
                <Select
                  placeholder="Select schema (optional)"
                  allowClear
                  showSearch
                  options={allSchemas.map(schema => ({
                    label: schema,
                    value: schema
                  }))}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                label="SNIP Level"
                name="snip_level"
                rules={[{ required: true }]}
              >
                <Select>
                  <Select.Option value="SNIP1">SNIP1 - Basic</Select.Option>
                  <Select.Option value="SNIP2">SNIP2 - Enhanced</Select.Option>
                  <Select.Option value="SNIP3">SNIP3 - Standard</Select.Option>
                  <Select.Option value="SNIP4">SNIP4 - Strict</Select.Option>
                  <Select.Option value="SNIP5">SNIP5 - Maximum</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                label="Generate TA1"
                name="generate_ta1"
                valuePropName="checked"
              >
                <Switch checkedChildren="Enabled" unCheckedChildren="Disabled" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                label="Generate 999"
                name="generate_999"
                valuePropName="checked"
              >
                <Switch checkedChildren="Enabled" unCheckedChildren="Disabled" />
              </Form.Item>
            </Col>
          </Row>

          <Divider>Matching Criteria</Divider>
          <Alert
            message="Profile Matching"
            description="Define criteria to automatically select this profile for incoming EDI documents"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />

          <Form.List name="criteria">
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name, ...restField }) => (
                  <Row key={key} gutter={[8, 8]} align="middle">
                    <Col xs={24} sm={6}>
                      <Form.Item
                        {...restField}
                        name={[name, "field_source"]}
                        rules={[{ required: true }]}
                      >
                        <Select placeholder="Source">
                          <Select.Option value="ISA">ISA Segment</Select.Option>
                          <Select.Option value="GS">GS Segment</Select.Option>
                          <Select.Option value="FILENAME">File Name</Select.Option>
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col xs={24} sm={5}>
                      <Form.Item
                        {...restField}
                        name={[name, "field_identifier"]}
                        rules={[{ required: true }]}
                      >
                        <Select placeholder="Field ID">
                          <Select.Option value="ISA01">ISA01 - Authorization Info Qualifier</Select.Option>
                          <Select.Option value="ISA02">ISA02 - Authorization Information</Select.Option>
                          <Select.Option value="ISA03">ISA03 - Security Info Qualifier</Select.Option>
                          <Select.Option value="ISA04">ISA04 - Security Information</Select.Option>
                          <Select.Option value="ISA05">ISA05 - Sender ID Qualifier</Select.Option>
                          <Select.Option value="ISA06">ISA06 - Sender ID</Select.Option>
                          <Select.Option value="ISA07">ISA07 - Receiver ID Qualifier</Select.Option>
                          <Select.Option value="ISA08">ISA08 - Receiver ID</Select.Option>
                          <Select.Option value="ISA15">ISA15 - Test/Production</Select.Option>
                          <Select.Option value="GS01">GS01 - Functional ID Code</Select.Option>
                          <Select.Option value="GS02">GS02 - Application Sender Code</Select.Option>
                          <Select.Option value="GS03">GS03 - Application Receiver Code</Select.Option>
                          <Select.Option value="GS08">GS08 - Version/Release</Select.Option>
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col xs={24} sm={5}>
                      <Form.Item
                        {...restField}
                        name={[name, "operator"]}
                        rules={[{ required: true }]}
                      >
                        <Select placeholder="Operator">
                          <Select.Option value="EQUALS">Equals</Select.Option>
                          <Select.Option value="STARTS_WITH">Starts With</Select.Option>
                          <Select.Option value="CONTAINS">Contains</Select.Option>
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col xs={24} sm={6}>
                      <Form.Item
                        {...restField}
                        name={[name, "value"]}
                        rules={[{ required: true }]}
                      >
                        <Input placeholder="Expected Value" />
                      </Form.Item>
                    </Col>
                    <Col xs={24} sm={2}>
                      <Button
                        type="text"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => remove(name)}
                      />
                    </Col>
                  </Row>
                ))}
                <Button
                  type="dashed"
                  onClick={() => add()}
                  block
                  icon={<PlusOutlined />}
                  style={{ marginTop: 8 }}
                >
                  Add Matching Criterion
                </Button>
              </>
            )}
          </Form.List>
        </Form>
      </Modal>
    </div>
  );
};