import React, { useState } from "react";
import { 
  Card, 
  Button, 
  Input, 
  Upload, 
  Select, 
  Radio, 
  Space, 
  Divider, 
  Typography, 
  Alert, 
  Tag, 
  Table, 
  Spin,
  notification,
  Row,
  Col
} from "antd";
import { 
  UploadOutlined, 
  PlayCircleOutlined, 
  DownloadOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined
} from "@ant-design/icons";
import { useCustom } from "@refinedev/core";
import axios from "axios";

const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

interface ValidationResult {
  valid: boolean;
  status: string;
  matched_profile?: string;
  detection_method?: string;
  ta1_content?: string;
  ta1_999_content?: string;
  processing_time_ms?: number;
  schema_used?: string;
  snip_level_used?: string;
  findings?: Array<{
    level: string;
    code: string;
    message: string;
    location: {
      segment_id: string;
      segment_instance: number;
      element_position: number;
      line_number: number;
    };
  }>;
}

interface Profile {
  id: number;
  name: string;
  implementation_guide: string;
  snip_level: string;
  generate_ta1: boolean;
  generate_999: boolean;
}

export const ValidationHub: React.FC = () => {
  const [ediContent, setEdiContent] = useState<string>("");
  const [fileName, setFileName] = useState<string>("");
  const [profileMode, setProfileMode] = useState<"auto" | "manual">("auto");
  const [selectedProfile, setSelectedProfile] = useState<string | undefined>();
  const [isValidating, setIsValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);

  // Define standard validation profiles
  const profiles = [
    { name: 'auto-detect', description: 'Auto-detect format and validate' },
    { name: 'x12-5010', description: 'X12 5010 Standard' },
    { name: 'x12-4010', description: 'X12 4010 Standard' },
    { name: 'edifact', description: 'UN/EDIFACT Standard' },
    { name: 'custom', description: 'Custom validation rules' }
  ];

  const handleFileUpload = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      setEdiContent(e.target?.result as string);
      setFileName(file.name);
    };
    reader.readAsText(file);
    return false; // Prevent auto upload
  };

  const validateEDI = async () => {
    if (!ediContent.trim()) {
      notification.error({
        message: "Validation Error",
        description: "Please provide EDI content to validate"
      });
      return;
    }

    setIsValidating(true);
    try {
      const payload: any = {
        edi_data: ediContent,
        file_name: fileName || "validation_test.edi"
      };

      if (profileMode === "manual" && selectedProfile) {
        payload.profile_name = selectedProfile;
      }

      const response = await axios.post("/api/v1/validate", payload);
      setValidationResult(response.data);
      
      notification.success({
        message: "Validation Complete",
        description: `EDI validation completed in ${response.data.processing_time_ms}ms`
      });
    } catch (error: any) {
      notification.error({
        message: "Validation Failed",
        description: error.response?.data?.detail || "An error occurred during validation"
      });
      console.error("Validation error:", error);
    } finally {
      setIsValidating(false);
    }
  };

  const downloadResponse = (content: string, filename: string) => {
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const clearForm = () => {
    setEdiContent("");
    setFileName("");
    setValidationResult(null);
    setSelectedProfile(undefined);
  };

  return (
    <div style={{ padding: "24px" }}>
      <Title level={2}>🔍 Validation Hub</Title>
      <Paragraph>
        Quick validation interface for testing EDI documents with flexible profile selection.
        Supports both auto-detection and manual profile override.
      </Paragraph>

      <Row gutter={[24, 24]}>
        {/* Input Section */}
        <Col xs={24} lg={12}>
          <Card title="📄 EDI Input" size="small">
            <Space direction="vertical" style={{ width: "100%" }}>
              {/* Input Method Selection */}
              <div>
                <Text strong>Input Method:</Text>
                <Radio.Group 
                  value={ediContent ? "paste" : "upload"} 
                  style={{ marginLeft: 8 }}
                >
                  <Radio.Button value="paste">Paste EDI Text</Radio.Button>
                  <Radio.Button value="upload">Upload File</Radio.Button>
                </Radio.Group>
              </div>

              {/* File Upload */}
              <Upload
                accept=".edi,.x12,.txt"
                beforeUpload={handleFileUpload}
                maxCount={1}
                showUploadList={false}
              >
                <Button icon={<UploadOutlined />}>
                  Upload EDI File
                </Button>
              </Upload>
              
              {fileName && (
                <Tag color="blue" closable onClose={() => setFileName("")}>
                  📎 {fileName}
                </Tag>
              )}

              {/* EDI Content Input */}
              <TextArea
                placeholder="Paste your EDI content here or upload a file above..."
                value={ediContent}
                onChange={(e) => setEdiContent(e.target.value)}
                rows={8}
                style={{ fontFamily: "monospace", fontSize: "12px" }}
              />

              {/* Profile Selection */}
              <Divider />
              <div>
                <Text strong>Profile Selection:</Text>
                <Radio.Group 
                  value={profileMode} 
                  onChange={(e) => setProfileMode(e.target.value)}
                  style={{ marginLeft: 8, marginBottom: 8 }}
                >
                  <Radio.Button value="auto">Auto-detect</Radio.Button>
                  <Radio.Button value="manual">Manual Override</Radio.Button>
                </Radio.Group>
                
                {profileMode === "manual" && (
                  <Select
                    placeholder="Select a profile..."
                    value={selectedProfile}
                    onChange={setSelectedProfile}
                    style={{ width: "100%" }}
                    options={profiles.map(profile => ({
                      label: `${profile.name} (${profile.implementation_guide})`,
                      value: profile.name
                    }))}
                  />
                )}
              </div>

              {/* Action Buttons */}
              <Space>
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  loading={isValidating}
                  onClick={validateEDI}
                  size="large"
                >
                  Validate EDI
                </Button>
                <Button onClick={clearForm}>
                  Clear
                </Button>
              </Space>
            </Space>
          </Card>
        </Col>

        {/* Results Section */}
        <Col xs={24} lg={12}>
          <Card 
            title="📊 Validation Results" 
            size="small"
            extra={
              validationResult && (
                <Tag color={validationResult.valid ? "success" : "error"}>
                  {validationResult.valid ? "✅ Valid" : "❌ Invalid"}
                </Tag>
              )
            }
          >
            {isValidating && (
              <div style={{ textAlign: "center", padding: "40px" }}>
                <Spin size="large" />
                <div style={{ marginTop: 16 }}>
                  <Text>Validating EDI document...</Text>
                </div>
              </div>
            )}

            {!isValidating && !validationResult && (
              <div style={{ textAlign: "center", padding: "40px", color: "#8c8c8c" }}>
                <Text>Results will appear here after validation</Text>
              </div>
            )}

            {!isValidating && validationResult && (
              <Space direction="vertical" style={{ width: "100%" }}>
                {/* Status Alert */}
                <Alert
                  message={validationResult.status}
                  type={validationResult.valid ? "success" : "error"}
                  icon={validationResult.valid ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />}
                  showIcon
                />

                {/* Profile Info */}
                {validationResult.matched_profile && (
                  <Card size="small" title="🎯 Profile Information">
                    <Row gutter={[16, 8]}>
                      <Col span={12}>
                        <Text strong>Profile:</Text><br />
                        <Text>{validationResult.matched_profile}</Text>
                      </Col>
                      <Col span={12}>
                        <Text strong>Detection:</Text><br />
                        <Tag color={validationResult.detection_method === "auto" ? "blue" : "orange"}>
                          {validationResult.detection_method}
                        </Tag>
                      </Col>
                      <Col span={12}>
                        <Text strong>Schema:</Text><br />
                        <Text code>{validationResult.schema_used}</Text>
                      </Col>
                      <Col span={12}>
                        <Text strong>SNIP Level:</Text><br />
                        <Tag color="purple">{validationResult.snip_level_used}</Tag>
                      </Col>
                    </Row>
                  </Card>
                )}

                {/* Processing Metrics */}
                <Card size="small" title="⚡ Processing Metrics">
                  <Row gutter={[16, 8]}>
                    <Col span={12}>
                      <ClockCircleOutlined style={{ color: "#1890ff" }} />
                      <Text style={{ marginLeft: 8 }}>
                        {validationResult.processing_time_ms}ms
                      </Text>
                    </Col>
                    <Col span={12}>
                      <Text>File Size: {new Blob([ediContent]).size} bytes</Text>
                    </Col>
                  </Row>
                </Card>

                {/* Error Details */}
                {validationResult.findings && validationResult.findings.length > 0 && (
                  <Card size="small" title="⚠️ Validation Issues">
                    <Table
                      dataSource={validationResult.findings}
                      size="small"
                      pagination={false}
                      scroll={{ y: 200 }}
                    >
                      <Table.Column 
                        title="Level" 
                        dataIndex="level"
                        render={(level) => (
                          <Tag color={level === "error" ? "red" : level === "warning" ? "orange" : "blue"}>
                            {level}
                          </Tag>
                        )}
                      />
                      <Table.Column title="Message" dataIndex="message" />
                      <Table.Column 
                        title="Location" 
                        dataIndex="location"
                        render={(location) => `${location.segment_id}:${location.line_number}`}
                      />
                    </Table>
                  </Card>
                )}

                {/* Download Section */}
                {(validationResult.ta1_content || validationResult.ta1_999_content) && (
                  <Card size="small" title="📥 Generated Responses">
                    <Space>
                      {validationResult.ta1_content && (
                        <Button
                          icon={<DownloadOutlined />}
                          onClick={() => downloadResponse(validationResult.ta1_content!, "ta1_response.edi")}
                        >
                          Download TA1
                        </Button>
                      )}
                      {validationResult.ta1_999_content && (
                        <Button
                          icon={<DownloadOutlined />}
                          onClick={() => downloadResponse(validationResult.ta1_999_content!, "999_response.edi")}
                        >
                          Download 999
                        </Button>
                      )}
                    </Space>
                  </Card>
                )}
              </Space>
            )}
          </Card>
        </Col>
      </Row>

      {/* API Testing Panel */}
      <Card 
        title="🔧 API Testing" 
        size="small" 
        style={{ marginTop: 24 }}
      >
        <Space direction="vertical" style={{ width: "100%" }}>
          <Alert
            message="API Endpoint Information"
            description="POST /api/v1/validate - Enhanced validation endpoint with profile flexibility"
            type="info"
            showIcon
          />
          
          <div>
            <Text strong>Example cURL (Auto-detection):</Text>
            <TextArea
              readOnly
              value={`curl -X POST ${window.location.origin}/api/v1/validate \\
  -H "Authorization: Bearer <jwt_token>" \\
  -H "Content-Type: application/json" \\
  -H "X-Tenant-ID: tenant-a" \\
  -d '{
    "edi_data": "ISA*00*          *01*SECRET    *ZZ*SUBMITTER     *ZZ*RECEIVER      *230315*1430*^*00501*000000001*1*T*:~",
    "file_name": "test_claim.x12"
  }'`}
              rows={8}
              style={{ fontFamily: "monospace", fontSize: "12px" }}
            />
          </div>

          <div>
            <Text strong>Example cURL (Manual Override):</Text>
            <TextArea
              readOnly
              value={`curl -X POST ${window.location.origin}/api/v1/validate \\
  -H "Authorization: Bearer <jwt_token>" \\
  -H "Content-Type: application/json" \\  
  -H "X-Tenant-ID: tenant-a" \\
  -d '{
    "edi_data": "ISA*00*          *01*SECRET    *ZZ*SUBMITTER     *ZZ*RECEIVER      *230315*1430*^*00501*000000001*1*T*:~",
    "file_name": "test_claim.x12",
    "profile_name": "priority_claims"
  }'`}
              rows={9}
              style={{ fontFamily: "monospace", fontSize: "12px" }}
            />
          </div>
        </Space>
      </Card>
    </div>
  );
};