// FILE: admin-ui/src/pages/validation/Validation.tsx

import React, { useState, useMemo } from "react";
import {
  Card,
  Button,
  Input,
  Upload,
  Space,
  Typography,
  Alert,
  Tag,
  Descriptions,
  Table,
  Row,
  Col,
  Spin,
  notification,
  Select,
  Form,
  Divider,
} from "antd";
import {
  UploadOutlined,
  PlayCircleOutlined,
  DownloadOutlined,
  FileTextOutlined,
} from "@ant-design/icons";
import { useCustom } from "@refinedev/core";
import axios from "axios";

const { TextArea } = Input;
const { Title, Text } = Typography;

interface ValidationResult {
  valid: boolean;
  status: string;
  matched_profile?: string;
  ta1_content?: string;
  processing_time_ms?: number;
  schema_used?: string;
  snip_level_used?: string;
  findings?: Array<{
    level: string;
    code: string;
    message: string;
    location: any;
  }>;
}

interface Profile {
  id: number;
  name: string;
}

export const Validation: React.FC = () => {
  const [form] = Form.useForm();
  const [isValidating, setIsValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);

  const { data: profilesData, isLoading: isLoadingProfiles } = useCustom<Profile[]>({
    url: "/trading-partners",
    method: "get",
  });

  const allProfiles = useMemo(() => {
    if (!profilesData?.data) return [];
    return profilesData.data.flatMap((partner: any) => partner.profiles || []);
  }, [profilesData]);

  const handleFileUpload = (file: File) => {
    if (file.size > 10 * 1024 * 1024) {
      notification.error({ message: "File size exceeds 10MB limit." });
      return false;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      form.setFieldsValue({ edi_data: content });
    };
    reader.readAsText(file);
    return false;
  };
  
  const validateEDI = async (values: { edi_data: string, profile_name: string }) => {
    setIsValidating(true);
    setValidationResult(null);
    try {
      const payload = {
        edi_data: values.edi_data,
        profile_name: values.profile_name,
      };

      const response = await axios.post("/api/v1/validate", payload);
      setValidationResult(response.data);
      notification.success({ message: "Validation Complete" });
    } catch (error: any) {
      notification.error({
        message: "Validation Failed", 
        description: error.response?.data?.detail || "An error occurred during validation"
      });
    } finally {
      setIsValidating(false);
    }
  };

  const downloadResponse = (content: string, filename: string) => {
    try {
      const blob = new Blob([content], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error) {
      notification.error({ message: "Download Failed" });
    }
  };
  
  return (
    <Card>
      <Title level={4}>EDI Validator</Title>
      <Text type="secondary">Validate EDI data against a specific trading partner profile.</Text>
      
      <Form form={form} onFinish={validateEDI} layout="vertical" style={{ marginTop: 24 }}>
        <Row gutter={24}>
          <Col xs={24} md={12}>
            <Form.Item name="edi_data" rules={[{ required: true, message: "EDI data is required." }]}>
              <TextArea
                placeholder="Paste your EDI content here..."
                rows={12}
                style={{ fontFamily: "monospace", fontSize: "12px" }}
              />
            </Form.Item>
            <Upload accept=".edi,.x12,.txt" beforeUpload={handleFileUpload} maxCount={1} showUploadList={false}>
              <Button icon={<UploadOutlined />} style={{ marginBottom: 16 }}>
                Or Upload File
              </Button>
            </Upload>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item
              name="profile_name"
              label="Validation Profile"
              rules={[{ required: true, message: "Please select a validation profile." }]}
            >
              <Select
                placeholder="Select a profile..."
                loading={isLoadingProfiles}
                options={allProfiles.map(profile => ({
                  label: profile.name,
                  value: profile.name
                }))}
                showSearch
              />
            </Form.Item>
            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                icon={<PlayCircleOutlined />}
                loading={isValidating}
              >
                Validate EDI
              </Button>
            </Form.Item>
          </Col>
        </Row>
      </Form>

      <Divider />
      
      <Title level={5}>Results</Title>
      {isValidating ? (
        <div style={{ textAlign: "center", padding: 40 }}><Spin /></div>
      ) : !validationResult ? (
        <div style={{ textAlign: "center", padding: 40, color: "#8c8c8c" }}>
          <FileTextOutlined style={{ fontSize: 48, marginBottom: 16 }} />
          <div>Validation results will appear here.</div>
        </div>
      ) : (
        <Space direction="vertical" style={{ width: "100%" }}>
          <Alert
            message={validationResult.status}
            type={validationResult.valid ? "success" : "error"}
            showIcon
          />
          <Descriptions bordered size="small" column={2}>
            <Descriptions.Item label="Result">
              <Tag color={validationResult.valid ? "success" : "error"}>
                {validationResult.valid ? "Valid" : "Invalid"}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Processing Time">
              {validationResult.processing_time_ms}ms
            </Descriptions.Item>
            <Descriptions.Item label="Profile Used">
              {validationResult.matched_profile}
            </Descriptions.Item>
            <Descriptions.Item label="Schema Used">
              <Text code>{validationResult.schema_used}</Text>
            </Descriptions.Item>
          </Descriptions>

          {validationResult.findings && validationResult.findings.length > 0 && (
            <Table
              title={() => <Text strong>Validation Issues</Text>}
              dataSource={validationResult.findings}
              size="small"
              pagination={false}
              rowKey={(r, i) => `${r.code}-${i}`}
            >
              <Table.Column title="Level" dataIndex="level" width={100} render={(l) => <Tag>{l}</Tag>} />
              <Table.Column title="Code" dataIndex="code" width={150} />
              <Table.Column title="Message" dataIndex="message" />
            </Table>
          )}

          {validationResult.ta1_content && (
            <Button
              icon={<DownloadOutlined />}
              onClick={() => downloadResponse(validationResult.ta1_content!, "ta1_response.edi")}
            >
              Download TA1
            </Button>
          )}
        </Space>
      )}
    </Card>
  );
};