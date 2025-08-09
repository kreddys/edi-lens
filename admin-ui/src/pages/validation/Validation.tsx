import React, { useState } from "react";
import {
  Card,
  Button,
  Input,
  Upload,
  Radio,
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
  Divider
} from "antd";
import {
  UploadOutlined,
  PlayCircleOutlined,
  DownloadOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  ClockCircleOutlined,
  ExportOutlined,
  FileTextOutlined
} from "@ant-design/icons";
import { useCustom } from "@refinedev/core";
import axios from "axios";

const { TextArea } = Input;
const { Title, Text } = Typography;

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

interface EDIStructure {
  isa_segments: {
    sender_id: string;
    receiver_id: string;
    control_number: string;
    test_production: string;
  };
  gs_segments: {
    functional_id: string;
    sender_code: string;
    receiver_code: string;
  };
  transaction_summary: {
    transaction_count: number;
    file_size: string;
  };
}

export const Validation: React.FC = () => {
  const [ediContent, setEdiContent] = useState<string>("");
  const [fileName, setFileName] = useState<string>("");
  const [profileMode, setProfileMode] = useState<"auto" | "manual">("auto");
  const [selectedProfile, setSelectedProfile] = useState<string | undefined>();
  const [isValidating, setIsValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [ediStructure, setEdiStructure] = useState<EDIStructure | null>(null);

  // Debug logging for tests - removed to clean up test output

  // Fetch available profiles for manual selection
  const { data: profilesData } = useCustom<Profile[]>({
    url: "/trading-partners",
    method: "get",
  });

  const profiles = profilesData?.data || [];

  const handleFileUpload = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      setEdiContent(content);
      setFileName(file.name);
      
      // Auto-analyze EDI structure when content is loaded
      analyzeEDIStructure(content);
    };
    reader.readAsText(file);
    return false; // Prevent auto upload
  };

  const analyzeEDIStructure = (content: string) => {
    // Mock EDI structure analysis - in real implementation, this would parse the EDI
    if (content.trim()) {
      const mockStructure: EDIStructure = {
        isa_segments: {
          sender_id: "ISA06: SUBMITTER",
          receiver_id: "ISA08: RECEIVER",
          control_number: "ISA13: 000000001",
          test_production: "ISA15: T (Test)"
        },
        gs_segments: {
          functional_id: "GS01: HC (Healthcare Claims)",
          sender_code: "GS02: SENDER123", 
          receiver_code: "GS03: RECEIVER456"
        },
        transaction_summary: {
          transaction_count: 1,
          file_size: `${(new Blob([content]).size / 1024).toFixed(1)} KB`
        }
      };
      setEdiStructure(mockStructure);
    } else {
      setEdiStructure(null);
    }
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
      const validationData = response.data;
      setValidationResult(validationData);
      
      notification.success({
        message: "Validation Complete",
        description: `EDI validation completed in ${validationData?.processing_time_ms || 0}ms`
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
    try {
      const blob = new Blob([content], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      
      // Use event approach instead of DOM manipulation for testing compatibility
      if (typeof window !== 'undefined' && document.body) {
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else {
        // Fallback for test environments
        const event = new MouseEvent('click', {
          view: window,
          bubbles: true,
          cancelable: true,
        });
        link.dispatchEvent(event);
      }
      
      URL.revokeObjectURL(url);
    } catch (error) {
      console.warn('Download failed:', error);
      notification.error({
        message: "Download Failed",
        description: "Unable to download file. Please try again."
      });
    }
  };

  const exportValidationResults = () => {
    if (!validationResult) return;
    
    const exportData = {
      validation_summary: {
        valid: validationResult.valid,
        status: validationResult.status,
        processing_time_ms: validationResult.processing_time_ms,
        matched_profile: validationResult.matched_profile,
        detection_method: validationResult.detection_method,
        schema_used: validationResult.schema_used,
        snip_level_used: validationResult.snip_level_used
      },
      edi_structure: ediStructure,
      findings: validationResult.findings || [],
      timestamp: new Date().toISOString(),
      file_name: fileName
    };

    const jsonContent = JSON.stringify(exportData, null, 2);
    downloadResponse(jsonContent, `validation_report_${new Date().toISOString().split("T")[0]}.json`);
    
    notification.success({
      message: "Export Complete",
      description: "Validation results exported successfully"
    });
  };

  const clearForm = () => {
    setEdiContent("");
    setFileName("");
    setValidationResult(null);
    setEdiStructure(null);
    setSelectedProfile(undefined);
  };

  return (
    <div style={{ padding: "24px" }}>
      <Title level={2}>🔍 EDI Validation</Title>
      <Text style={{ color: "#666", display: "block", marginBottom: "24px" }}>
        Comprehensive EDI validation with structure analysis, profile matching, and response generation.
      </Text>

      <Row gutter={[24, 24]}>
        {/* Input Section */}
        <Col xs={24} lg={12}>
          <Card title="📄 EDI Input" size="small">
            <Space direction="vertical" style={{ width: "100%" }}>
              {/* File Upload */}
              <Upload
                accept=".edi,.x12,.txt"
                beforeUpload={handleFileUpload}
                maxCount={1}
                showUploadList={false}
              >
                <Button icon={<UploadOutlined />} block>
                  Upload EDI File
                </Button>
              </Upload>
              
              {fileName && (
                <Tag color="blue" closable onClose={() => {
                  setFileName("");
                  setEdiStructure(null);
                }}>
                  📎 {fileName}
                </Tag>
              )}

              {/* EDI Content Input */}
              <TextArea
                placeholder="Paste your EDI content here or upload a file above..."
                value={ediContent}
                onChange={(e) => {
                  setEdiContent(e.target.value);
                  analyzeEDIStructure(e.target.value);
                }}
                rows={10}
                style={{ fontFamily: "monospace", fontSize: "12px" }}
              />

              {/* Profile Selection */}
              <Divider />
              <div>
                <Text strong>Profile Selection:</Text>
                <Radio.Group 
                  value={profileMode} 
                  onChange={(e) => {
                    setProfileMode(e.target.value);
                  }}
                  style={{ marginLeft: 8, marginBottom: 8 }}
                >
                  <Radio.Button value="auto">Auto-detect Profile</Radio.Button>
                  <Radio.Button value="manual">Manual Selection</Radio.Button>
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
                  disabled={!ediContent.trim() || isValidating}
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

        {/* Analysis & Results Section */}
        <Col xs={24} lg={12}>
          <Space direction="vertical" style={{ width: "100%" }} size="middle">
            {/* EDI Structure Analysis */}
            {ediStructure && (
              <Card title="🏗️ EDI Structure Analysis" size="small">
                <Row gutter={[16, 16]}>
                  <Col xs={24} md={12}>
                    <Text strong>ISA Segments:</Text>
                    <Descriptions size="small" column={1} style={{ marginTop: 8 }}>
                      <Descriptions.Item label="Sender ID">
                        <Text code>{ediStructure.isa_segments.sender_id}</Text>
                      </Descriptions.Item>
                      <Descriptions.Item label="Receiver ID">
                        <Text code>{ediStructure.isa_segments.receiver_id}</Text>
                      </Descriptions.Item>
                      <Descriptions.Item label="Control Number">
                        <Text code>{ediStructure.isa_segments.control_number}</Text>
                      </Descriptions.Item>
                      <Descriptions.Item label="Test/Production">
                        <Tag color={ediStructure.isa_segments.test_production.includes("T") ? "orange" : "green"}>
                          {ediStructure.isa_segments.test_production}
                        </Tag>
                      </Descriptions.Item>
                    </Descriptions>
                  </Col>
                  <Col xs={24} md={12}>
                    <Text strong>GS Segments:</Text>
                    <Descriptions size="small" column={1} style={{ marginTop: 8 }}>
                      <Descriptions.Item label="Functional ID">
                        <Text code>{ediStructure.gs_segments.functional_id}</Text>
                      </Descriptions.Item>
                      <Descriptions.Item label="Sender Code">
                        <Text code>{ediStructure.gs_segments.sender_code}</Text>
                      </Descriptions.Item>
                      <Descriptions.Item label="Receiver Code">
                        <Text code>{ediStructure.gs_segments.receiver_code}</Text>
                      </Descriptions.Item>
                    </Descriptions>
                    
                    <Divider />
                    <Text strong>Summary:</Text>
                    <Descriptions size="small" column={1} style={{ marginTop: 8 }}>
                      <Descriptions.Item label="Transactions">
                        {ediStructure.transaction_summary.transaction_count}
                      </Descriptions.Item>
                      <Descriptions.Item label="File Size">
                        {ediStructure.transaction_summary.file_size}
                      </Descriptions.Item>
                    </Descriptions>
                  </Col>
                </Row>
              </Card>
            )}

            {/* Validation Results */}
            <Card 
              title="📊 Validation Results" 
              size="small"
              extra={
                validationResult && (
                  <Space>
                    <Button
                      icon={<ExportOutlined />}
                      onClick={exportValidationResults}
                      size="small"
                    >
                      Export Results
                    </Button>
                    <Tag color={validationResult.valid ? "success" : "error"}>
                      {validationResult.valid ? "✅ Valid" : "❌ Invalid"}
                    </Tag>
                  </Space>
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

              {!isValidating && !validationResult && !ediStructure && (
                <div style={{ textAlign: "center", padding: "40px", color: "#8c8c8c" }}>
                  <FileTextOutlined style={{ fontSize: "48px", marginBottom: "16px" }} />
                  <div>
                    <Text>Upload or paste EDI content to see analysis and validation results</Text>
                  </div>
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

                  {/* Profile Match Info */}
                  {validationResult.matched_profile && (
                    <Card size="small" title="🎯 Profile Match Information">
                      <Row gutter={[16, 8]}>
                        <Col span={12}>
                          <Text strong>Matched Profile:</Text><br />
                          <Text>{validationResult.matched_profile}</Text>
                        </Col>
                        <Col span={12}>
                          <Text strong>Detection Method:</Text><br />
                          <Tag color={validationResult.detection_method === "auto" ? "blue" : "orange"}>
                            {validationResult.detection_method}
                          </Tag>
                        </Col>
                        <Col span={12}>
                          <Text strong>Schema Used:</Text><br />
                          <Text code style={{ fontSize: "11px" }}>{validationResult.schema_used}</Text>
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
                        <Text>File Size: {ediStructure?.transaction_summary.file_size || 'N/A'}</Text>
                      </Col>
                    </Row>
                  </Card>

                  {/* Validation Issues */}
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
                          width={80}
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
                          width={100}
                          render={(location) => `${location.segment_id}:${location.line_number}`}
                        />
                      </Table>
                    </Card>
                  )}

                  {/* Download Responses */}
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
          </Space>
        </Col>
      </Row>
    </div>
  );
};