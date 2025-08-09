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
  Progress,
  Table,
  Row,
  Col,
  Spin,
  notification
} from "antd";
import {
  ExperimentOutlined,
  UploadOutlined,
  PlayCircleOutlined,
  DownloadOutlined,
  ClearOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined
} from "@ant-design/icons";

const { TextArea } = Input;
const { Text } = Typography;

interface TestResult {
  validation_outcome: "PASS" | "FAIL";
  schema_coverage: number;
  unused_elements: string[];
  validation_errors: Array<{
    level: string;
    code: string;
    message: string;
    location: {
      segment_id: string;
      line_number: number;
    };
  }>;
  snip_level_used: string;
  ta1_generated: boolean;
  ta1_999_generated: boolean;
  ta1_content?: string;
  ta1_999_content?: string;
  processing_time_ms: number;
}

interface SchemaTesterProps {
  selectedSchema?: string;
}

export const SchemaTester: React.FC<SchemaTesterProps> = ({ selectedSchema }) => {
  const [ediContent, setEdiContent] = useState<string>("");
  const [fileName, setFileName] = useState<string>("");
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  const handleFileUpload = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      setEdiContent(e.target?.result as string);
      setFileName(file.name);
    };
    reader.readAsText(file);
    return false; // Prevent auto upload
  };

  const testSchema = async () => {
    if (!selectedSchema || !ediContent.trim()) {
      notification.error({
        message: "Test Error",
        description: "Please select a schema and provide EDI content to test"
      });
      return;
    }

    setIsTesting(true);
    
    // Simulate API call to test schema - in real implementation, this would call the validation API
    setTimeout(() => {
      const mockResult: TestResult = {
        validation_outcome: "PASS",
        schema_coverage: 87,
        unused_elements: ["REF*6R", "DTP*573", "N3*Additional Address Line"],
        validation_errors: [
          {
            level: "warning",
            code: "W001",
            message: "Optional element REF*6R not used in transaction",
            location: { segment_id: "REF", line_number: 12 }
          }
        ],
        snip_level_used: "SNIP3",
        ta1_generated: true,
        ta1_999_generated: false,
        ta1_content: "ISA*00*          *01*SECRET    *ZZ*SUBMITTER     *ZZ*RECEIVER      *230315*1430*^*00501*000000001*1*T*:~TA1*000000001*A*000*~",
        processing_time_ms: 245
      };

      setTestResult(mockResult);
      setIsTesting(false);
      
      notification.success({
        message: "Schema Test Complete",
        description: `Schema validation completed in ${mockResult.processing_time_ms}ms with ${mockResult.schema_coverage}% coverage`
      });
    }, 2000);
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

  const clearTest = () => {
    setEdiContent("");
    setFileName("");
    setTestResult(null);
  };

  if (!selectedSchema) {
    return (
      <Card size="small">
        <div style={{ textAlign: "center", padding: "40px", color: "#8c8c8c" }}>
          <ExperimentOutlined style={{ fontSize: "48px", marginBottom: "16px" }} />
          <div>
            <Text>Select a schema to test validation against EDI content</Text>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card 
      title={
        <Space>
          <ExperimentOutlined />
          <span>Schema Tester</span>
          <Tag color="blue">{selectedSchema}</Tag>
        </Space>
      }
      size="small"
    >
      <Row gutter={[24, 24]}>
        {/* Input Section */}
        <Col xs={24} lg={12}>
          <Space direction="vertical" style={{ width: "100%" }}>
            <Alert
              message="Test Schema Against EDI"
              description="Upload or paste EDI content to test validation against the selected schema"
              type="info"
              showIcon
            />

            <Upload
              accept=".edi,.x12,.txt"
              beforeUpload={handleFileUpload}
              maxCount={1}
              showUploadList={false}
            >
              <Button icon={<UploadOutlined />} block>
                Upload Test EDI File
              </Button>
            </Upload>
            
            {fileName && (
              <Tag color="blue" closable onClose={() => setFileName("")}>
                📎 {fileName}
              </Tag>
            )}

            <TextArea
              placeholder="Or paste your EDI content here for testing..."
              value={ediContent}
              onChange={(e) => setEdiContent(e.target.value)}
              rows={10}
              style={{ fontFamily: "monospace", fontSize: "11px" }}
            />

            <Space>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                loading={isTesting}
                onClick={testSchema}
              >
                Test Schema
              </Button>
              <Button 
                icon={<ClearOutlined />} 
                onClick={clearTest}
              >
                Clear
              </Button>
            </Space>
          </Space>
        </Col>

        {/* Results Section */}
        <Col xs={24} lg={12}>
          {isTesting && (
            <Card size="small" title="🧪 Testing...">
              <div style={{ textAlign: "center", padding: "40px" }}>
                <Spin size="large" />
                <div style={{ marginTop: 16 }}>
                  <Text>Testing schema validation...</Text>
                </div>
              </div>
            </Card>
          )}

          {!isTesting && !testResult && (
            <Card size="small" title="📊 Test Results">
              <div style={{ textAlign: "center", padding: "40px", color: "#8c8c8c" }}>
                <Text>Test results will appear here after validation</Text>
              </div>
            </Card>
          )}

          {!isTesting && testResult && (
            <Space direction="vertical" style={{ width: "100%" }}>
              {/* Test Outcome */}
              <Alert
                message={`Validation ${testResult.validation_outcome}`}
                type={testResult.validation_outcome === "PASS" ? "success" : "error"}
                icon={testResult.validation_outcome === "PASS" ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />}
                showIcon
              />

              {/* Schema Coverage */}
              <Card size="small" title="📊 Schema Coverage">
                <Progress 
                  percent={testResult.schema_coverage} 
                  status={testResult.schema_coverage > 80 ? "success" : "normal"}
                  format={(percent) => `${percent}% coverage`}
                />
                <Text style={{ fontSize: "12px", color: "#666" }}>
                  {testResult.schema_coverage}% of schema elements used in this transaction
                </Text>
              </Card>

              {/* Test Configuration */}
              <Card size="small" title="⚙️ Test Configuration">
                <Row gutter={[16, 8]}>
                  <Col span={12}>
                    <Text strong>SNIP Level:</Text><br />
                    <Tag color="purple">{testResult.snip_level_used}</Tag>
                  </Col>
                  <Col span={12}>
                    <Text strong>Processing Time:</Text><br />
                    <Text>{testResult.processing_time_ms}ms</Text>
                  </Col>
                  <Col span={12}>
                    <Text strong>TA1 Generated:</Text><br />
                    <Tag color={testResult.ta1_generated ? "success" : "default"}>
                      {testResult.ta1_generated ? "Yes" : "No"}
                    </Tag>
                  </Col>
                  <Col span={12}>
                    <Text strong>999 Generated:</Text><br />
                    <Tag color={testResult.ta1_999_generated ? "success" : "default"}>
                      {testResult.ta1_999_generated ? "Yes" : "No"}
                    </Tag>
                  </Col>
                </Row>
              </Card>

              {/* Validation Issues */}
              {testResult.validation_errors.length > 0 && (
                <Card size="small" title="⚠️ Validation Issues">
                  <Table
                    dataSource={testResult.validation_errors}
                    size="small"
                    pagination={false}
                    scroll={{ y: 150 }}
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

              {/* Unused Elements */}
              {testResult.unused_elements.length > 0 && (
                <Card size="small" title="📋 Unused Schema Elements">
                  <Space wrap>
                    {testResult.unused_elements.map((element, index) => (
                      <Tag key={index} color="default" style={{ fontSize: "11px" }}>
                        {element}
                      </Tag>
                    ))}
                  </Space>
                  <div style={{ marginTop: 8 }}>
                    <Text style={{ fontSize: "12px", color: "#666" }}>
                      These schema elements were not used in the test transaction
                    </Text>
                  </div>
                </Card>
              )}

              {/* Download Responses */}
              {(testResult.ta1_content || testResult.ta1_999_content) && (
                <Card size="small" title="📥 Generated Responses">
                  <Space>
                    {testResult.ta1_content && (
                      <Button
                        icon={<DownloadOutlined />}
                        onClick={() => downloadResponse(testResult.ta1_content!, "test_ta1_response.edi")}
                      >
                        Download TA1
                      </Button>
                    )}
                    {testResult.ta1_999_content && (
                      <Button
                        icon={<DownloadOutlined />}
                        onClick={() => downloadResponse(testResult.ta1_999_content!, "test_999_response.edi")}
                      >
                        Download 999
                      </Button>
                    )}
                  </Space>
                </Card>
              )}
            </Space>
          )}
        </Col>
      </Row>
    </Card>
  );
};