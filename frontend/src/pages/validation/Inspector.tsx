import React, { useState } from "react";
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
  Divider,
  Spin,
  notification
} from "antd";
import {
  SearchOutlined,
  UploadOutlined,
  ClearOutlined,
  PlayCircleOutlined,
  FileTextOutlined
} from "@ant-design/icons";

const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

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

interface ProfileMatch {
  name: string;
  confidence: string;
  matching_criteria: Array<{
    field: string;
    expected: string;
    actual: string;
    status: string;
  }>;
  profile_config: {
    schema: string;
    snip_level: string;
    ta1_enabled: boolean;
    ta1_999_enabled: boolean;
  };
}

interface InspectionResult {
  edi_structure: EDIStructure;
  matched_profile?: ProfileMatch;
  no_match_explanation?: {
    message: string;
    available_profiles: Array<{
      name: string;
      why_not_matched: string;
    }>;
    suggestion: string;
  };
  validation_preview: {
    would_use_schema: string;
    would_use_snip_level: string;
    would_generate_ta1: boolean;
    would_generate_999: boolean;
    estimated_errors: string;
  };
}

export const Inspector: React.FC = () => {
  const [ediContent, setEdiContent] = useState<string>("");
  const [fileName, setFileName] = useState<string>("");
  const [isInspecting, setIsInspecting] = useState(false);
  const [inspectionResult, setInspectionResult] = useState<InspectionResult | null>(null);

  const handleFileUpload = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      setEdiContent(e.target?.result as string);
      setFileName(file.name);
    };
    reader.readAsText(file);
    return false; // Prevent auto upload
  };

  const inspectEDI = async () => {
    if (!ediContent.trim()) {
      notification.error({
        message: "Inspection Error",
        description: "Please provide EDI content to inspect"
      });
      return;
    }

    setIsInspecting(true);
    
    // Simulate inspection process - in real implementation, this would call an API
    setTimeout(() => {
      // Mock inspection result based on EDI content analysis
      const mockResult: InspectionResult = {
        edi_structure: {
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
            file_size: `${(new Blob([ediContent]).size / 1024).toFixed(1)} KB`
          }
        },
        matched_profile: {
          name: "Healthcare Claims Standard",
          confidence: "High Match",
          matching_criteria: [
            { field: "ISA06", expected: "SUBMITTER", actual: "SUBMITTER", status: "✅ Match" },
            { field: "GS01", expected: "HC", actual: "HC", status: "✅ Match" }
          ],
          profile_config: {
            schema: "837P_X222A1_custom",
            snip_level: "SNIP3",
            ta1_enabled: true,
            ta1_999_enabled: false
          }
        },
        validation_preview: {
          would_use_schema: "837P_X222A1_custom",
          would_use_snip_level: "SNIP3",
          would_generate_ta1: true,
          would_generate_999: false,
          estimated_errors: "0 syntax errors detected in preview"
        }
      };

      setInspectionResult(mockResult);
      setIsInspecting(false);
      
      notification.success({
        message: "Inspection Complete",
        description: "EDI structure analysis completed successfully"
      });
    }, 2000);
  };

  const clearInspection = () => {
    setEdiContent("");
    setFileName("");
    setInspectionResult(null);
  };

  const runFullValidation = () => {
    notification.info({
      message: "Navigation",
      description: "Redirecting to Validation Hub for full validation..."
    });
    // In real implementation, this would navigate to ValidationHub with pre-filled data
  };

  return (
    <div style={{ padding: "24px" }}>
      <Title level={2}>🔬 EDI Inspector</Title>
      <Paragraph>
        Analyze EDI document structure, test profile matching, and preview validation settings 
        before running full validation.
      </Paragraph>

      <Row gutter={[24, 24]}>
        {/* Input Section */}
        <Col xs={24} lg={8}>
          <Card title="📄 EDI Input" size="small">
            <Space direction="vertical" style={{ width: "100%" }}>
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
                <Tag color="blue" closable onClose={() => setFileName("")}>
                  📎 {fileName}
                </Tag>
              )}

              <TextArea
                placeholder="Paste your EDI content here..."
                value={ediContent}
                onChange={(e) => setEdiContent(e.target.value)}
                rows={12}
                style={{ fontFamily: "monospace", fontSize: "11px" }}
              />

              <Space>
                <Button
                  type="primary"
                  icon={<SearchOutlined />}
                  loading={isInspecting}
                  onClick={inspectEDI}
                >
                  Inspect EDI
                </Button>
                <Button 
                  icon={<ClearOutlined />} 
                  onClick={clearInspection}
                >
                  Clear
                </Button>
              </Space>
            </Space>
          </Card>
        </Col>

        {/* Analysis Results */}
        <Col xs={24} lg={16}>
          {isInspecting && (
            <Card title="🔍 Analyzing..." size="small">
              <div style={{ textAlign: "center", padding: "40px" }}>
                <Spin size="large" />
                <div style={{ marginTop: 16 }}>
                  <Text>Analyzing EDI structure and matching profiles...</Text>
                </div>
              </div>
            </Card>
          )}

          {!isInspecting && !inspectionResult && (
            <Card title="📊 Analysis Results" size="small">
              <div style={{ textAlign: "center", padding: "40px", color: "#8c8c8c" }}>
                <FileTextOutlined style={{ fontSize: "48px", marginBottom: "16px" }} />
                <div>
                  <Text>Analysis results will appear here after inspection</Text>
                </div>
              </div>
            </Card>
          )}

          {!isInspecting && inspectionResult && (
            <Space direction="vertical" style={{ width: "100%" }} size="large">
              {/* EDI Structure Analysis */}
              <Card title="🏗️ EDI File Structure" size="small">
                <Row gutter={[16, 16]}>
                  <Col xs={24} md={12}>
                    <Descriptions title="ISA Segments" size="small" column={1}>
                      <Descriptions.Item label="Sender ID">
                        <Text code>{inspectionResult.edi_structure.isa_segments.sender_id}</Text>
                      </Descriptions.Item>
                      <Descriptions.Item label="Receiver ID">
                        <Text code>{inspectionResult.edi_structure.isa_segments.receiver_id}</Text>
                      </Descriptions.Item>
                      <Descriptions.Item label="Control Number">
                        <Text code>{inspectionResult.edi_structure.isa_segments.control_number}</Text>
                      </Descriptions.Item>
                      <Descriptions.Item label="Test/Production">
                        <Tag color={inspectionResult.edi_structure.isa_segments.test_production.includes("T") ? "orange" : "green"}>
                          {inspectionResult.edi_structure.isa_segments.test_production}
                        </Tag>
                      </Descriptions.Item>
                    </Descriptions>
                  </Col>
                  <Col xs={24} md={12}>
                    <Descriptions title="GS Segments" size="small" column={1}>
                      <Descriptions.Item label="Functional ID">
                        <Text code>{inspectionResult.edi_structure.gs_segments.functional_id}</Text>
                      </Descriptions.Item>
                      <Descriptions.Item label="Sender Code">
                        <Text code>{inspectionResult.edi_structure.gs_segments.sender_code}</Text>
                      </Descriptions.Item>
                      <Descriptions.Item label="Receiver Code">
                        <Text code>{inspectionResult.edi_structure.gs_segments.receiver_code}</Text>
                      </Descriptions.Item>
                    </Descriptions>
                    
                    <Divider />
                    <Descriptions title="Summary" size="small" column={1}>
                      <Descriptions.Item label="Transaction Count">
                        {inspectionResult.edi_structure.transaction_summary.transaction_count}
                      </Descriptions.Item>
                      <Descriptions.Item label="File Size">
                        {inspectionResult.edi_structure.transaction_summary.file_size}
                      </Descriptions.Item>
                    </Descriptions>
                  </Col>
                </Row>
              </Card>

              {/* Profile Matching Results */}
              <Card title="🎯 Profile Matching Results" size="small">
                {inspectionResult.matched_profile ? (
                  <Space direction="vertical" style={{ width: "100%" }}>
                    <Alert
                      message={`Profile Match: ${inspectionResult.matched_profile.name}`}
                      description={`Confidence: ${inspectionResult.matched_profile.confidence}`}
                      type="success"
                      showIcon
                    />
                    
                    <Row gutter={[16, 16]}>
                      <Col xs={24} md={12}>
                        <Card size="small" title="Matching Criteria">
                          <Table
                            dataSource={inspectionResult.matched_profile.matching_criteria}
                            size="small"
                            pagination={false}
                          >
                            <Table.Column title="Field" dataIndex="field" />
                            <Table.Column title="Expected" dataIndex="expected" />
                            <Table.Column title="Actual" dataIndex="actual" />
                            <Table.Column 
                              title="Status" 
                              dataIndex="status"
                              render={(status) => (
                                <Tag color={status.includes("✅") ? "success" : "error"}>
                                  {status}
                                </Tag>
                              )}
                            />
                          </Table>
                        </Card>
                      </Col>
                      <Col xs={24} md={12}>
                        <Card size="small" title="Profile Configuration">
                          <Descriptions size="small" column={1}>
                            <Descriptions.Item label="Schema">
                              <Text code>{inspectionResult.matched_profile.profile_config.schema}</Text>
                            </Descriptions.Item>
                            <Descriptions.Item label="SNIP Level">
                              <Tag color="purple">{inspectionResult.matched_profile.profile_config.snip_level}</Tag>
                            </Descriptions.Item>
                            <Descriptions.Item label="TA1 Generation">
                              <Tag color={inspectionResult.matched_profile.profile_config.ta1_enabled ? "success" : "default"}>
                                {inspectionResult.matched_profile.profile_config.ta1_enabled ? "Enabled" : "Disabled"}
                              </Tag>
                            </Descriptions.Item>
                            <Descriptions.Item label="999 Generation">
                              <Tag color={inspectionResult.matched_profile.profile_config.ta1_999_enabled ? "success" : "default"}>
                                {inspectionResult.matched_profile.profile_config.ta1_999_enabled ? "Enabled" : "Disabled"}
                              </Tag>
                            </Descriptions.Item>
                          </Descriptions>
                        </Card>
                      </Col>
                    </Row>
                  </Space>
                ) : (
                  <Alert
                    message="No Profile Match Found"
                    description={inspectionResult.no_match_explanation?.message}
                    type="warning"
                    showIcon
                  />
                )}
              </Card>

              {/* Validation Preview */}
              <Card title="🔮 Validation Preview" size="small">
                <Row gutter={[16, 16]}>
                  <Col xs={24} md={12}>
                    <Descriptions size="small" column={1}>
                      <Descriptions.Item label="Would use schema">
                        <Text code>{inspectionResult.validation_preview.would_use_schema}</Text>
                      </Descriptions.Item>
                      <Descriptions.Item label="Would use SNIP level">
                        <Tag color="purple">{inspectionResult.validation_preview.would_use_snip_level}</Tag>
                      </Descriptions.Item>
                      <Descriptions.Item label="Would generate TA1">
                        <Tag color={inspectionResult.validation_preview.would_generate_ta1 ? "success" : "default"}>
                          {inspectionResult.validation_preview.would_generate_ta1 ? "Yes" : "No"}
                        </Tag>
                      </Descriptions.Item>
                      <Descriptions.Item label="Would generate 999">
                        <Tag color={inspectionResult.validation_preview.would_generate_999 ? "success" : "default"}>
                          {inspectionResult.validation_preview.would_generate_999 ? "Yes" : "No"}
                        </Tag>
                      </Descriptions.Item>
                    </Descriptions>
                  </Col>
                  <Col xs={24} md={12}>
                    <Alert
                      message="Estimated Issues"
                      description={inspectionResult.validation_preview.estimated_errors}
                      type="info"
                      showIcon
                    />
                  </Col>
                </Row>
              </Card>

              {/* Action Buttons */}
              <Card title="⚡ Actions" size="small">
                <Space wrap>
                  <Button
                    type="primary"
                    icon={<PlayCircleOutlined />}
                    onClick={runFullValidation}
                  >
                    Run Full Validation Test
                  </Button>
                  <Button>Create Profile From This EDI</Button>
                  <Button>Save as Test Case</Button>
                </Space>
              </Card>
            </Space>
          )}
        </Col>
      </Row>
    </div>
  );
};