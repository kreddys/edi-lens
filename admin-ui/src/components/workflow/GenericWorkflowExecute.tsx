import React, { useState, useEffect } from "react";
import { 
  Card, 
  Button, 
  Input, 
  Upload, 
  Space, 
  Typography, 
  Alert, 
  Tag, 
  Row, 
  Col, 
  Spin,
  App,
  Form,
  Switch,
  Select,
  InputNumber,
  Divider
} from "antd";
import { 
  UploadOutlined, 
  PlayCircleOutlined, 
  DownloadOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined
} from "@ant-design/icons";
import { useDataProvider } from "@refinedev/core";

const { TextArea } = Input;
const { Title, Text } = Typography;

// Type definitions
interface ProcessingOption {
  name: string;
  type: 'boolean' | 'string' | 'number' | 'select';
  label: string;
  description?: string;
  default_value?: any;
  options?: string[];
  required?: boolean;
  min_value?: number;
  max_value?: number;
  pattern?: string;
}

interface InputConfiguration {
  title: string;
  accepted_file_types: string[];
  placeholder_text: string;
  supports_text_input: boolean;
  supports_file_upload: boolean;
  max_file_size_mb?: number;
  input_validation?: string;
}

interface OutputConfiguration {
  name: string;
  label: string;
  type: 'download' | 'display' | 'status';
  description?: string;
  file_extension?: string;
  icon?: string;
}

interface WorkflowUIConfiguration {
  input: InputConfiguration;
  processing_options: ProcessingOption[];
  outputs: OutputConfiguration[];
  theme?: Record<string, string>;
  help_text?: string;
}

interface ProcessingOutput {
  name: string;
  type: 'download' | 'display' | 'status';
  label: string;
  content?: string;
  download_filename?: string;
  mime_type?: string;
  file_extension?: string;
  metadata?: Record<string, any>;
}

interface ProcessingResult {
  success: boolean;
  outputs: ProcessingOutput[];
  processing_time_ms: number;
  workflow_id: string;
  processed_at: string;
  validation_results?: Array<{
    level: string;
    code: string;
    message: string;
  }>;
  request_id?: string;
}

interface GenericWorkflowExecuteProps {
  workflowId: string;
  templateId: string;
}

export const GenericWorkflowExecute: React.FC<GenericWorkflowExecuteProps> = ({ 
  workflowId, 
  templateId 
}) => {
  const [fileContent, setFileContent] = useState<string>("");
  const [fileType, setFileType] = useState<string>("");
  const [processingOptions, setProcessingOptions] = useState<Record<string, any>>({});
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState<ProcessingResult | null>(null);
  const [uiConfig, setUIConfig] = useState<WorkflowUIConfiguration | null>(null);
  const [isLoadingConfig, setIsLoadingConfig] = useState(true);
  
  const { notification } = App.useApp();
  const dataProvider = useDataProvider();

  // Load UI configuration from template
  useEffect(() => {
    const loadTemplateConfig = async () => {
      setIsLoadingConfig(true);
      try {
        const result = await dataProvider().getOne({
          resource: "workflow-templates",
          id: templateId
        });
        
        if (result?.data?.ui_configuration) {
          setUIConfig(result.data.ui_configuration);
          
          // Set default processing options
          const defaults: Record<string, any> = {};
          result.data.ui_configuration.processing_options?.forEach((option: ProcessingOption) => {
            if (option.default_value !== undefined) {
              defaults[option.name] = option.default_value;
            }
          });
          setProcessingOptions(defaults);
        } else {
          // Fallback to basic configuration if no UI config is provided
          setUIConfig({
            input: {
              title: "📄 File Input",
              accepted_file_types: [],
              placeholder_text: "Paste your content here or upload a file...",
              supports_text_input: true,
              supports_file_upload: true
            },
            processing_options: [],
            outputs: []
          });
        }
      } catch (error) {
        notification.error({
          message: "Configuration Error",
          description: "Failed to load workflow configuration"
        });
        console.error("Failed to load template config:", error);
      } finally {
        setIsLoadingConfig(false);
      }
    };

    if (templateId) {
      loadTemplateConfig();
    }
  }, [templateId, dataProvider, notification]);

  const getFileTypeFromExtension = (extension?: string): string => {
    if (!extension) return "";
    
    const extensionMap: Record<string, string> = {
      'edi': 'edi',
      'x12': 'edi',
      'json': 'json',
      'csv': 'csv',
      'tsv': 'csv',
      'xml': 'xml',
      'txt': 'text',
      'log': 'log',
      'yaml': 'yaml',
      'yml': 'yaml',
      'pdf': 'pdf',
      'doc': 'document',
      'docx': 'document',
      'xls': 'spreadsheet',
      'xlsx': 'spreadsheet',
      'png': 'image',
      'jpg': 'image',
      'jpeg': 'image',
      'gif': 'image'
    };
    
    return extensionMap[extension.toLowerCase()] || extension.toLowerCase();
  };

  const handleFileUpload = (file: File) => {
    if (uiConfig?.input.max_file_size_mb && file.size > uiConfig.input.max_file_size_mb * 1024 * 1024) {
      notification.error({
        message: "File Too Large",
        description: `File size exceeds ${uiConfig.input.max_file_size_mb}MB limit`
      });
      return false;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      setFileContent(e.target?.result as string);
      
      // Auto-detect file type from extension
      const extension = file.name.split('.').pop();
      setFileType(getFileTypeFromExtension(extension));
    };
    reader.readAsText(file);
    return false; // Prevent auto upload
  };

  const executeWorkflow = async () => {
    if (!fileContent.trim()) {
      notification.error({
        message: "Execution Error",
        description: `Please provide ${uiConfig?.input.title.toLowerCase() || 'content'} to process`
      });
      return;
    }

    setIsExecuting(true);
    try {
      const result = await dataProvider().custom!({
        url: `/workflows/${workflowId}/process`,
        method: "post",
        payload: {
          content: fileContent,
          file_type: fileType,
          processing_options: processingOptions,
          metadata: {
            original_filename: "user_upload",
            upload_timestamp: new Date().toISOString(),
            file_size: new Blob([fileContent]).size
          }
        }
      });

      if (result?.data) {
        // Type assertion to ProcessingResult since we know the structure
        setExecutionResult(result.data as ProcessingResult);
        
        notification.success({
          message: "Processing Complete",
          description: `Workflow executed in ${result.data.processing_time_ms}ms`
        });
      }
    } catch (error: any) {
      notification.error({
        message: "Processing Failed",
        description: error.message || "An error occurred during processing"
      });
      console.error("Execution error:", error);
    } finally {
      setIsExecuting(false);
    }
  };

  const renderProcessingOptions = () => {
    if (!uiConfig?.processing_options || uiConfig.processing_options.length === 0) {
      return null;
    }

    return (
      <Card title="⚙️ Processing Options" size="small" style={{ marginTop: 16 }}>
        <Form layout="vertical">
          {uiConfig.processing_options.map((option) => (
            <Form.Item
              key={option.name}
              label={option.label}
              help={option.description}
              required={option.required}
            >
              {renderOptionControl(option)}
            </Form.Item>
          ))}
        </Form>
      </Card>
    );
  };

  const renderOptionControl = (option: ProcessingOption) => {
    const value = processingOptions[option.name];
    const onChange = (newValue: any) => {
      setProcessingOptions(prev => ({
        ...prev,
        [option.name]: newValue
      }));
    };

    switch (option.type) {
      case 'boolean':
        return (
          <Switch
            checked={value}
            onChange={onChange}
          />
        );
      case 'select':
        return (
          <Select
            value={value}
            onChange={onChange}
            options={option.options?.map(opt => ({ label: opt, value: opt }))}
            style={{ width: '100%' }}
            placeholder={`Select ${option.label.toLowerCase()}`}
          />
        );
      case 'number':
        return (
          <InputNumber
            value={value}
            onChange={onChange}
            min={option.min_value}
            max={option.max_value}
            style={{ width: '100%' }}
            placeholder={`Enter ${option.label.toLowerCase()}`}
          />
        );
      default:
        return (
          <Input
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={`Enter ${option.label.toLowerCase()}`}
          />
        );
    }
  };

  const downloadOutput = (output: ProcessingOutput) => {
    if (!output.content) return;
    
    const blob = new Blob([output.content], { 
      type: output.mime_type || "text/plain" 
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = output.download_filename || `${output.name}${output.file_extension || '.txt'}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const renderOutputs = () => {
    if (!executionResult?.outputs || executionResult.outputs.length === 0) {
      return null;
    }

    return (
      <Space direction="vertical" style={{ width: "100%" }}>
        {/* Processing Summary */}
        <Alert
          message={executionResult.success ? "Processing Successful" : "Processing Completed with Issues"}
          type={executionResult.success ? "success" : "error"}
          icon={executionResult.success ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />}
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
              <Text strong>{new Blob([fileContent]).size} bytes</Text>
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

        {/* Validation Results */}
        {executionResult.validation_results && executionResult.validation_results.length > 0 && (
          <Card size="small" title="⚠️ Validation Issues">
            <Space direction="vertical" style={{ width: "100%" }}>
              {executionResult.validation_results.map((result, index) => (
                <Alert
                  key={index}
                  message={`${result.code}: ${result.message}`}
                  type={result.level === "error" ? "error" : result.level === "warning" ? "warning" : "info"}
                  showIcon
                  style={{ fontSize: '12px' }}
                />
              ))}
            </Space>
          </Card>
        )}

        {/* Generated Outputs */}
        {executionResult.outputs.map((output) => (
          <Card key={output.name} size="small" title={`📄 ${output.label}`}>
            {output.type === 'display' && (
              <div style={{ 
                maxHeight: '200px', 
                overflow: 'auto', 
                backgroundColor: '#f5f5f5', 
                padding: '8px', 
                borderRadius: '4px' 
              }}>
                <Text style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '12px' }}>
                  {output.content}
                </Text>
              </div>
            )}
            {output.type === 'download' && (
              <Space>
                <Button
                  icon={<DownloadOutlined />}
                  onClick={() => downloadOutput(output)}
                  type="primary"
                >
                  Download {output.label}
                </Button>
                {output.content && (
                  <Text type="secondary">
                    Size: {new Blob([output.content]).size} bytes
                  </Text>
                )}
              </Space>
            )}
            {output.type === 'status' && (
              <Tag color={output.content === 'success' ? 'green' : 'red'}>
                {output.content}
              </Tag>
            )}
          </Card>
        ))}
      </Space>
    );
  };

  if (isLoadingConfig) {
    return (
      <div style={{ textAlign: 'center', padding: '40px' }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>
          <Text>Loading workflow configuration...</Text>
        </div>
      </div>
    );
  }

  if (!uiConfig) {
    return (
      <Alert
        message="Configuration Error"
        description="Unable to load workflow configuration. Please try again."
        type="error"
        showIcon
      />
    );
  }

  return (
    <div style={{ padding: "24px" }}>
      <Title level={2}>Execute Workflow</Title>
      
      {uiConfig.help_text && (
        <Alert
          message="Workflow Information"
          description={uiConfig.help_text}
          type="info"
          icon={<InfoCircleOutlined />}
          style={{ marginBottom: 24 }}
          showIcon
        />
      )}
      
      <Row gutter={[24, 24]}>
        {/* Dynamic Input Section */}
        <Col xs={24} lg={12}>
          <Card title={uiConfig.input.title} size="small">
            <Space direction="vertical" style={{ width: "100%" }}>
              {uiConfig.input.supports_file_upload && (
                <Upload
                  accept={uiConfig.input.accepted_file_types.length > 0 ? uiConfig.input.accepted_file_types.join(',') : undefined}
                  beforeUpload={handleFileUpload}
                  maxCount={1}
                  showUploadList={false}
                >
                  <Button icon={<UploadOutlined />}>
                    Upload File
                    {uiConfig.input.accepted_file_types.length > 0 && (
                      <span style={{ marginLeft: 8, color: '#999' }}>
                        ({uiConfig.input.accepted_file_types.join(', ')})
                      </span>
                    )}
                  </Button>
                </Upload>
              )}

              {uiConfig.input.supports_text_input && (
                <TextArea
                  placeholder={uiConfig.input.placeholder_text}
                  value={fileContent}
                  onChange={(e) => setFileContent(e.target.value)}
                  rows={12}
                  style={{ fontFamily: "monospace", fontSize: "12px" }}
                />
              )}

              {uiConfig.input.max_file_size_mb && (
                <Text type="secondary" style={{ fontSize: '12px' }}>
                  Maximum file size: {uiConfig.input.max_file_size_mb}MB
                </Text>
              )}

              <Divider />

              <Space>
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  loading={isExecuting}
                  onClick={executeWorkflow}
                  size="large"
                >
                  Execute Workflow
                </Button>
                <Button onClick={() => { 
                  setFileContent(""); 
                  setExecutionResult(null); 
                  setFileType("");
                }}>
                  Clear
                </Button>
              </Space>
            </Space>
          </Card>

          {renderProcessingOptions()}
        </Col>

        {/* Dynamic Results Section */}
        <Col xs={24} lg={12}>
          <Card 
            title="📊 Processing Results" 
            size="small"
            extra={
              executionResult && (
                <Tag color={executionResult.success ? "success" : "error"}>
                  {executionResult.success ? "✅ Success" : "❌ Failed"}
                </Tag>
              )
            }
          >
            {isExecuting && (
              <div style={{ textAlign: "center", padding: "40px" }}>
                <Spin size="large" />
                <div style={{ marginTop: 16 }}>
                  <Text>Processing...</Text>
                </div>
              </div>
            )}

            {!isExecuting && !executionResult && (
              <div style={{ textAlign: "center", padding: "40px", color: "#8c8c8c" }}>
                <Text>Results will appear here after processing</Text>
              </div>
            )}

            {!isExecuting && executionResult && renderOutputs()}
          </Card>
        </Col>
      </Row>
    </div>
  );
};