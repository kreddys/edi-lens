// FILE: admin-ui/src/pages/tradingPartners/TradingPartnerForm.tsx

import React, { useState, useEffect, useMemo } from "react";
import {
  Card, Form, Input, Button, Space, Typography, Select, Switch,
  Divider, Row, Col, Alert, Table, Modal, Checkbox, // <-- ADDED Checkbox
} from "antd";
import {
  SaveOutlined, PlusOutlined, EditOutlined, DeleteOutlined,
} from "@ant-design/icons";
import { useCreate, useUpdate, useCustom, HttpError, useApiUrl } from "@refinedev/core";

const { Title } = Typography; // <-- REMOVED unused Text
// const { TextArea } = Input; // <-- REMOVED unused TextArea

// --- Interfaces ---
interface PartnerProfile {
  id?: number;
  name: string;
  validation_schema_name: string;
  snip_level: "SNIP1" | "SNIP2" | "SNIP3" | "SNIP4" | "SNIP5";
  generate_ta1: boolean;
  generate_999: boolean;
  file_name_patterns?: string;
}

export interface TradingPartnerData {
  id?: number;
  name: string;
  description?: string;
  profiles: PartnerProfile[];
  sftp_enabled: boolean;
  sftp_username?: string;
}

interface TradingPartnerFormProps {
  initialData?: TradingPartnerData;
  mode: "create" | "edit";
  onSuccess?: () => void;
}

export const TradingPartnerForm: React.FC<TradingPartnerFormProps> = ({
  initialData,
  mode,
  onSuccess,
}) => {
  const [form] = Form.useForm<TradingPartnerData>();
  const [profiles, setProfiles] = useState<PartnerProfile[]>([]);
  const [isProfileModalVisible, setIsProfileModalVisible] = useState(false);
  const [editingProfile, setEditingProfile] = useState<{ profile: Partial<PartnerProfile>; index?: number } | null>(null);
  const [profileForm] = Form.useForm<PartnerProfile>();

  const { mutate: createPartner, isLoading: isCreating } = useCreate();
  const { mutate: updatePartner, isLoading: isUpdating } = useUpdate();

  const apiUrl = useApiUrl();
  const { data: schemasData, isLoading: isLoadingSchemas } = useCustom<{
    base_schemas: string[];
    specialized_schemas: string[];
  }>({ 
    url: `${apiUrl}/schemas`,
    method: "get" 
  });

  const schemaOptions = useMemo(() => {
    if (!schemasData?.data) return [];
    const { base_schemas = [], specialized_schemas = [] } = schemasData.data;
    const options = [];
    if (base_schemas.length > 0) {
        options.push({ label: "Base Schemas", options: base_schemas.map((f: string) => ({ label: f, value: f })) });
    }
    if (specialized_schemas.length > 0) {
        options.push({ label: "Specialized Schemas", options: specialized_schemas.map((f: string) => ({ label: f, value: f })) });
    }
    return options;
  }, [schemasData]);
  
  useEffect(() => {
    if (initialData) {
      form.setFieldsValue(initialData);
      setProfiles(initialData.profiles || []);
    }
  }, [initialData, form]);

  const handleFinish = (values: TradingPartnerData) => {
    const finalPayload = { ...values, profiles };
    const mutationConfig = {
      resource: "trading-partners",
      values: finalPayload,
      onSuccess: () => { onSuccess?.(); },
      successNotification: () => ({ message: `Trading Partner ${mode === "create" ? "created" : "updated"}`, type: "success" as "success" }),
      errorNotification: (error?: HttpError) => ({ message: `Error`, description: error?.message, type: "error" as "error" }),
    };
    if (mode === "create") createPartner(mutationConfig);
    else updatePartner({ ...mutationConfig, id: initialData?.id as number });
  };

  const handleAddProfile = () => {
    profileForm.resetFields();
    profileForm.setFieldsValue({
      snip_level: "SNIP3", generate_ta1: true, generate_999: false, file_name_patterns: '["*.edi"]',
    });
    setEditingProfile({ profile: {} });
    setIsProfileModalVisible(true);
  };
  
  const handleEditProfile = (profile: PartnerProfile, index: number) => {
    profileForm.setFieldsValue(profile);
    setEditingProfile({ profile, index });
    setIsProfileModalVisible(true);
  };

  const handleDeleteProfile = (index: number) => {
    setProfiles(current => current.filter((_, i) => i !== index));
  };

  const handleSaveProfile = async () => {
    try {
      const formValues = await profileForm.validateFields();
      setProfiles(current => {
        const newProfiles = [...current];
        if (editingProfile?.index !== undefined) newProfiles[editingProfile.index] = formValues;
        else newProfiles.push(formValues);
        return newProfiles;
      });
      setIsProfileModalVisible(false);
      setEditingProfile(null);
    } catch (error) {
      console.error("Profile validation failed:", error);
    }
  };
  
  const sftpEnabled = Form.useWatch('sftp_enabled', form);

  return (
    <>
      <Form form={form} layout="vertical" onFinish={handleFinish} initialValues={{ sftp_enabled: false, profiles: [] }}>
        <Card
          title={mode === "create" ? "Create New Trading Partner" : `Edit Trading Partner: ${initialData?.name}`}
          actions={[
            <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={isCreating || isUpdating}>
              {mode === "create" ? "Create Partner" : "Save Changes"}
            </Button>
          ]}
        >
          <Title level={5}>Partner Details</Title>
          <Row gutter={24}>
            <Col xs={24} md={12}>
              <Form.Item label="Partner Name" name="name" rules={[{ required: true }]}>
                <Input placeholder="e.g., United Health Group" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="Description" name="description">
                <Input placeholder="Optional description" />
              </Form.Item>
            </Col>
          </Row>
          
          <Divider orientation="left" plain>SFTP Configuration</Divider>
          <Row gutter={24} align="middle">
            <Col xs={24} md={8}>
              <Form.Item name="sftp_enabled" valuePropName="checked" noStyle>
                <Checkbox>Enable SFTP Access</Checkbox>
              </Form.Item>
            </Col>
            <Col xs={24} md={16}>
              <Form.Item 
                label="SFTP Username" 
                name="sftp_username" 
                rules={[{ required: sftpEnabled, message: "Username is required when SFTP is enabled" }]}
                tooltip="This username will be created in SFTPGo upon saving."
              >
                <Input placeholder="e.g., tenant-a_uhg_claims" disabled={!sftpEnabled} />
              </Form.Item>
            </Col>
          </Row>

          <Divider orientation="left" plain>Validation Profiles</Divider>
          <Alert message="Configure processing rules for different EDI documents. For SFTP, the first profile with a matching filename pattern will be used." type="info" showIcon style={{ marginBottom: 16 }} />
          <Table
            dataSource={profiles.map((p, i) => ({ ...p, key: i }))}
            pagination={false}
            size="small"
            bordered
            footer={() => 
                <Button 
                    type="dashed" 
                    onClick={handleAddProfile} 
                    icon={<PlusOutlined />} 
                    block 
                    loading={isLoadingSchemas}
                >
                    Add Profile
                </Button>
            }
          >
            <Table.Column title="Profile Name" dataIndex="name" key="name" />
            <Table.Column title="Validation Schema" dataIndex="validation_schema_name" key="validation_schema_name" />
            <Table.Column title="Actions" key="actions" render={(_, record: PartnerProfile, index: number) => (
              <Space>
                <Button icon={<EditOutlined />} size="small" onClick={() => handleEditProfile(record, index)} />
                <Button icon={<DeleteOutlined />} size="small" danger onClick={() => handleDeleteProfile(index)} />
              </Space>
            )} />
          </Table>
        </Card>
      </Form>
      
      <Modal
        title={editingProfile?.index !== undefined ? "Edit Profile" : "Add New Profile"}
        open={isProfileModalVisible}
        onCancel={() => setIsProfileModalVisible(false)}
        onOk={handleSaveProfile}
        width={700}
        destroyOnClose
      >
        <Form form={profileForm} layout="vertical">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="Profile Name" name="name" rules={[{ required: true }]}>
                <Input placeholder="e.g., UHC Professional Claims" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item 
                label="Validation Schema" 
                name="validation_schema_name" 
                rules={[{ required: true, message: 'A validation schema is required.' }]}
              >
                <Select 
                  placeholder="Select a schema" 
                  loading={isLoadingSchemas}
                  allowClear 
                  showSearch 
                  options={schemaOptions}
                />
              </Form.Item>
            </Col>
            <Col span={24}>
              <Form.Item label="File Name Patterns (for SFTP)" name="file_name_patterns" tooltip='JSON array, e.g., ["claims_*.edi"]'>
                <Input placeholder='e.g., ["claims_*", "837p_*"]' />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="SNIP Level" name="snip_level" rules={[{ required: true }]}>
                <Select options={["SNIP1", "SNIP2", "SNIP3", "SNIP4", "SNIP5"].map(s => ({ label: s, value: s }))} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="Generate TA1" name="generate_ta1" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="Generate 999" name="generate_999" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>
    </>
  );
};