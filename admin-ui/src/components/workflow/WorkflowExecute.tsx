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
  Table, 
  Row, 
  Col, 
  Spin,
  App
} from "antd";
import { 
  UploadOutlined, 
  PlayCircleOutlined, 
  DownloadOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined
} from "@ant-design/icons";
import { useDataProvider } from "@refinedev/core";

const { TextArea } = Input;
const { Title, Text } = Typography;

interface ValidationResult {
  valid: boolean;
  validation_results: Array<{
    level: string;
    code: string;
  }>;
  ta1_acknowledgment?: string;
  ack999_acknowledgment?: string;
  processing_time_ms: number;
  request_id?: string;
  workflow_id: string;
  processed_at: string;
}

export const WorkflowExecute: React.FC<{ workflowId: string }> = ({ workflowId }) => {
  const [ediContent, setEdiContent] = useState<string>("");
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState<ValidationResult | null>(null);
  const { notification } = App.useApp();
  
  const dataProvider = useDataProvider();

  const handleFileUpload = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      setEdiContent(e.target?.result as string);
    };
    reader.readAsText(file);
    return false; // Prevent auto upload
  };

  const executeWorkflowProcess = async () => {
    if (!ediContent.trim()) {
      notification.error({
        message: "Execution Error",
        description: "Please provide EDI content to process"
      });
      return;
    }

    setIsExecuting(true);
    try {
      // Use data provider for API call
      const result = await dataProvider().custom!({
        url: `/workflows/${workflowId}/process`,
        method: "post",
        payload: {
          edi_content: ediContent,
          processing_options: {
            generate_ta1: true,
            generate_999: true
          }
        }
      });

      if (result?.data) {
        setExecutionResult(result.data);
        
        notification.success({
          message: "Execution Complete",
          description: `Workflow executed in ${result.data.processing_time_ms}ms`
        });
      }
    } catch (error: any) {
      notification.error({
        message: "Execution Failed",
        description: error.message || "An error occurred during execution"
      });
      console.error("Execution error:", error);
    } finally {
      setIsExecuting(false);
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
    setExecutionResult(null);
  };

  return (
    <div style={{ padding: "24px" }}>
      <Title level={2}>Execute Workflow</Title>
      
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
                <Button icon={<UploadOutlined />}>
                  Upload EDI File
                </Button>
              </Upload>

              {/* EDI Content Input */}
              <TextArea
                placeholder="Paste your EDI content here or upload a file above..."
                value={ediContent}
                onChange={(e) => setEdiContent(e.target.value)}
                rows={12}
                style={{ fontFamily: "monospace", fontSize: "12px" }}
              />

              {/* Action Buttons */}
              <Space>
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  loading={isExecuting}
                  onClick={executeWorkflowProcess}
                  size="large"
                >
                  Execute Workflow
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
            title="📊 Execution Results" 
            size="small"
            extra={
              executionResult && (
                <Tag color={executionResult.valid ? "success" : "error"}>
                  {executionResult.valid ? "✅ Valid" : "❌ Invalid"}
                </Tag>
              )
            }
          >
            {isExecuting && (
              <div style={{ textAlign: "center", padding: "40px" }}>
                <Spin size="large" />
                <div style={{ marginTop: 16 }}>
                  <Text>Executing workflow...</Text>
                </div>
              </div>
            )}

            {!isExecuting && !executionResult && (
              <div style={{ textAlign: "center", padding: "40px", color: "#8c8c8c" }}>
                <Text>Results will appear here after execution</Text>
              </div>
            )}

            {!isExecuting && executionResult && (
              <Space direction="vertical" style={{ width: "100%" }}>
                {/* Status Alert */}
                <Alert
                  message={executionResult.valid ? "Processing Successful" : "Processing Completed with Issues"}
                  type={executionResult.valid ? "success" : "error"}
                  icon={executionResult.valid ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />}
                  showIcon
                />

                {/* Processing Metrics */}
                <Card size="small" title="⚡ Processing Metrics">
                  <Row gutter={[16, 8]}>
                    <Col span={12}>
                      <Text>Processing Time:</Text><br />
                      <Text strong>{executionResult.processing_time_ms}ms</Text>
                    </Col>
                    <Col span={12}>
                      <Text>File Size:</Text><br />
                      <Text strong>{new Blob([ediContent]).size} bytes</Text>
                    </Col>
                    <Col span={12}>
                      <Text>Workflow ID:</Text><br />
                      <Text code>{executionResult.workflow_id}</Text>
                    </Col>
                    <Col span={12}>
                      <Text>Processed At:</Text><br />
                      <Text>{new Date(executionResult.processed_at).toLocaleString()}</Text>
                    </Col>
                  </Row>
                </Card>

                {/* Validation Issues */}
                {executionResult.validation_results && executionResult.validation_results.length > 0 && (
                  <Card size="small" title="⚠️ Validation Issues">
                    <Table
                      dataSource={executionResult.validation_results}
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
                      <Table.Column title="Code" dataIndex="code" />
                    </Table>
                  </Card>
                )}

                {/* Download Section */}
                {(executionResult.ta1_acknowledgment || executionResult.ack999_acknowledgment) && (
                  <Card size="small" title="📥 Generated Responses">
                    <Space>
                      {executionResult.ta1_acknowledgment && (
                        <Button
                          icon={<DownloadOutlined />}
                          onClick={() => downloadResponse(executionResult.ta1_acknowledgment!, "ta1_response.edi")}
                        >
                          Download TA1
                        </Button>
                      )}
                      {executionResult.ack999_acknowledgment && (
                        <Button
                          icon={<DownloadOutlined />}
                          onClick={() => downloadResponse(executionResult.ack999_acknowledgment!, "999_response.edi")}
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
    </div>
  );
};