import React, { useState } from 'react';
import {
  Card,
  Form,
  Input,
  Select,
  Switch,
  Button,
  Space,
  Typography,
  Divider,
  Row,
  Col,
  Alert,
  Upload,
  message,
  Spin,
  Tag,
  Progress,
  Modal,
  Descriptions,
} from 'antd';
import {
  PlayCircleOutlined,
  StopOutlined,
  ReloadOutlined,
  UploadOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  DownloadOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import { useApiUrl, useCustom } from '@refinedev/core';
import type { UploadProps } from 'antd';

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;
const { TextArea } = Input;

interface EdiBatchProcessorProps {
  workflowId?: string;
  templateId?: string;
  onWorkflowCreate?: (workflow: any) => void;
  onExecutionComplete?: (result: any) => void;
}

interface ProcessingResult {
  success: boolean;
  outputs: Array<{
    name: string;
    type: 'download' | 'display' | 'status';
    label: string;
    content?: string;
    download_filename?: string;
    mime_type?: string;
    file_extension?: string;
  }>;
  processing_time_ms: number;
  workflow_id: string;
  processed_at: string;
  validation_results?: any[];
}

interface WorkflowStatus {
  workflow_id: string;
  status: 'RUNNING' | 'STOPPED' | 'FAILED' | 'PENDING' | 'UNKNOWN';
  nifi_status?: string;
  deployment_status?: string;
  health_check?: {
    status: string;
    issues: string[];
  };
}

export const EdiBatchProcessor: React.FC<EdiBatchProcessorProps> = ({
  workflowId,
  templateId = 'edi-batch-processor-v2',
  onWorkflowCreate,
  onExecutionComplete,
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [currentWorkflowId, setCurrentWorkflowId] = useState(workflowId);
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus | null>(null);
  const [processingResult, setProcessingResult] = useState<ProcessingResult | null>(null);
  const [fileContent, setFileContent] = useState<string>('');
  const [fileName, setFileName] = useState<string>('');
  const [showStatusModal, setShowStatusModal] = useState(false);

  const apiUrl = useApiUrl();

  // Custom hooks for API calls
  const { mutate: createWorkflow } = useCustom({
    url: `${apiUrl}/workflows`,
    method: 'post',
  });

  const { mutate: executeWorkflow } = useCustom({
    url: `${apiUrl}/workflows/${currentWorkflowId}/execute`,
    method: 'post',
  });

  const { mutate: getWorkflowStatus } = useCustom({
    url: `${apiUrl}/workflows/${currentWorkflowId}/status`,
    method: 'get',
  });

  const { mutate: stopWorkflow } = useCustom({
    url: `${apiUrl}/workflows/${currentWorkflowId}/stop`,
    method: 'post',
  });

  // Handle file upload
  const uploadProps: UploadProps = {
    name: 'file',
    multiple: false,
    accept: '.edi,.x12,.txt',
    beforeUpload: (file) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const content = e.target?.result as string;
        setFileContent(content);
        setFileName(file.name);
        message.success(`File ${file.name} loaded successfully`);
      };
      reader.readAsText(file);
      return false; // Prevent automatic upload
    },
    onDrop: (e) => {
      console.log('Dropped files', e.dataTransfer.files);
    },
  };

  // Create workflow with configuration
  const handleCreateWorkflow = async (values: any) => {
    setLoading(true);
    try {
      const workflowConfig = {
        name: values.workflowName || `EDI Batch Processor - ${new Date().toISOString()}`,
        description: values.description || 'EDI batch processing workflow',
        template_id: templateId,
        configuration: {
          // GetFile Configuration
          input_directory: values.input_directory,
          filename_filter: values.filename_filter,
          polling_interval: values.polling_interval,
          keep_source_file: values.keep_source_file,
          
          // EDI Processor Configuration
          validation_schema: values.validation_schema,
          snip_level: values.snip_level,
          generate_cdm: values.generate_cdm,
          generate_ta1: values.generate_ta1,
          force_ta1: values.force_ta1,
          cdm_include_metadata: values.cdm_include_metadata,
          
          // PutFile Configuration
          output_directory: values.output_directory,
          output_filename_strategy: values.output_filename_strategy,
          custom_filename_pattern: values.custom_filename_pattern,
          conflict_resolution: values.conflict_resolution,
          
          // Advanced Configuration
          max_concurrent_tasks: values.max_concurrent_tasks,
        },
      };

      createWorkflow(
        { values: workflowConfig },
        {
          onSuccess: (data) => {
            const workflow = data.data;
            setCurrentWorkflowId(workflow.workflow_id);
            message.success('Workflow created successfully!');
            onWorkflowCreate?.(workflow);
          },
          onError: (error) => {
            console.error('Failed to create workflow:', error);
            message.error('Failed to create workflow');
          },
        }
      );
    } catch (error) {
      console.error('Error creating workflow:', error);
      message.error('Failed to create workflow');
    } finally {
      setLoading(false);
    }
  };

  // Execute workflow
  const handleExecuteWorkflow = async () => {
    if (!currentWorkflowId) {
      message.error('Please create a workflow first');
      return;
    }

    setExecuting(true);
    try {
      executeWorkflow(
        {
          values: {
            enable_monitoring: true,
            monitoring_interval_seconds: 30,
          },
        },
        {
          onSuccess: (data) => {
            const result = data.data;
            setWorkflowStatus({
              workflow_id: result.workflow_id,
              status: result.status,
              nifi_status: result.nifi_status,
              deployment_status: 'DEPLOYED',
            });
            message.success('Workflow started successfully!');
            
            // Start polling for status updates
            pollWorkflowStatus();
          },
          onError: (error) => {
            console.error('Failed to execute workflow:', error);
            message.error('Failed to execute workflow');
          },
        }
      );
    } catch (error) {
      console.error('Error executing workflow:', error);
      message.error('Failed to execute workflow');
    } finally {
      setExecuting(false);
    }
  };

  // Poll workflow status
  const pollWorkflowStatus = () => {
    const interval = setInterval(() => {
      if (currentWorkflowId) {
        getWorkflowStatus(
          {},
          {
            onSuccess: (data) => {
              const status = data.data;
              setWorkflowStatus(status);
              
              // Stop polling if workflow is no longer running
              if (status.status === 'STOPPED' || status.status === 'FAILED') {
                clearInterval(interval);
              }
            },
            onError: (error) => {
              console.error('Failed to get workflow status:', error);
              clearInterval(interval);
            },
          }
        );
      }
    }, 5000); // Poll every 5 seconds

    // Clean up interval after 5 minutes
    setTimeout(() => clearInterval(interval), 300000);
  };

  // Stop workflow
  const handleStopWorkflow = async () => {
    if (!currentWorkflowId) return;

    try {
      stopWorkflow(
        {},
        {
          onSuccess: () => {
            message.success('Workflow stopped successfully!');
            setWorkflowStatus(prev => prev ? { ...prev, status: 'STOPPED' } : null);
          },
          onError: (error) => {
            console.error('Failed to stop workflow:', error);
            message.error('Failed to stop workflow');
          },
        }
      );
    } catch (error) {
      console.error('Error stopping workflow:', error);
      message.error('Failed to stop workflow');
    }
  };

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'RUNNING': return 'green';
      case 'STOPPED': return 'default';
      case 'FAILED': return 'red';
      case 'PENDING': return 'orange';
      default: return 'default';
    }
  };

  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'RUNNING': return <CheckCircleOutlined />;
      case 'STOPPED': return <StopOutlined />;
      case 'FAILED': return <ExclamationCircleOutlined />;
      case 'PENDING': return <Spin size="small" />;
      default: return null;
    }
  };

  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>
        <FileTextOutlined /> EDI Batch Processor
      </Title>
      <Paragraph>
        Configure and execute batch EDI processing workflows using the consolidated EDI Processor.
        This workflow monitors a directory for EDI files, validates them, generates CDM and TA1 outputs,
        and saves results to designated directories.
      </Paragraph>

      <Row gutter={[24, 24]}>
        {/* Configuration Panel */}
        <Col xs={24} lg={16}>
          <Card title="Workflow Configuration" loading={loading}>
            <Form
              form={form}
              layout="vertical"
              onFinish={handleCreateWorkflow}
              initialValues={{
                polling_interval: '10 sec',
                filename_filter: '.*\\.(edi|x12|txt)$',
                validation_schema: '837.5010.X222.A1.json',
                snip_level: 3,
                generate_cdm: true,
                generate_ta1: false,
                force_ta1: false,
                cdm_include_metadata: true,
                output_filename_strategy: 'timestamp_prefix',
                conflict_resolution: 'replace',
                max_concurrent_tasks: 1,
                keep_source_file: false,
              }}
            >
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    label="Workflow Name"
                    name="workflowName"
                    rules={[{ required: true, message: 'Please enter workflow name' }]}
                  >
                    <Input placeholder="Enter workflow name" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="Description" name="description">
                    <Input placeholder="Optional description" />
                  </Form.Item>
                </Col>
              </Row>

              <Divider orientation="left">Input Configuration</Divider>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    label="Input Directory"
                    name="input_directory"
                    rules={[{ required: true, message: 'Please enter input directory' }]}
                  >
                    <Input placeholder="/data/input" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="Filename Filter" name="filename_filter">
                    <Input placeholder=".*\.(edi|x12|txt)$" />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="Polling Interval" name="polling_interval">
                    <Select>
                      <Option value="5 sec">5 seconds</Option>
                      <Option value="10 sec">10 seconds</Option>
                      <Option value="30 sec">30 seconds</Option>
                      <Option value="1 min">1 minute</Option>
                      <Option value="5 min">5 minutes</Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="Keep Source File" name="keep_source_file" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </Col>
              </Row>

              <Divider orientation="left">EDI Processing Configuration</Divider>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="Validation Schema" name="validation_schema">
                    <Select>
                      <Option value="837.5010.X222.A1.json">837P - Healthcare Claims</Option>
                      <Option value="835.5010.X221.A1.json">835 - Payment Remittance</Option>
                      <Option value="270.5010.X279.A1.json">270 - Eligibility Inquiry</Option>
                      <Option value="271.5010.X279.A1.json">271 - Eligibility Response</Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="SNIP Level" name="snip_level">
                    <Select>
                      <Option value={1}>Level 1 - Basic</Option>
                      <Option value={2}>Level 2 - Standard</Option>
                      <Option value={3}>Level 3 - Comprehensive</Option>
                      <Option value={4}>Level 4 - Strict</Option>
                      <Option value={5}>Level 5 - Maximum</Option>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={6}>
                  <Form.Item label="Generate CDM" name="generate_cdm" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="Generate TA1" name="generate_ta1" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="Force TA1" name="force_ta1" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="Include Metadata" name="cdm_include_metadata" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </Col>
              </Row>

              <Divider orientation="left">Output Configuration</Divider>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    label="Output Directory"
                    name="output_directory"
                    rules={[{ required: true, message: 'Please enter output directory' }]}
                  >
                    <Input placeholder="/data/output" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="Filename Strategy" name="output_filename_strategy">
                    <Select>
                      <Option value="original">Keep Original Name</Option>
                      <Option value="timestamp_prefix">Add Timestamp Prefix</Option>
                      <Option value="timestamp_suffix">Add Timestamp Suffix</Option>
                      <Option value="custom">Custom Pattern</Option>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="Conflict Resolution" name="conflict_resolution">
                    <Select>
                      <Option value="replace">Replace Existing</Option>
                      <Option value="ignore">Ignore Conflicts</Option>
                      <Option value="fail">Fail on Conflict</Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="Max Concurrent Tasks" name="max_concurrent_tasks">
                    <Select>
                      <Option value={1}>1 Task</Option>
                      <Option value={2}>2 Tasks</Option>
                      <Option value={5}>5 Tasks</Option>
                      <Option value={10}>10 Tasks</Option>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item>
                <Space>
                  <Button 
                    type="primary" 
                    htmlType="submit" 
                    loading={loading}
                    disabled={!!currentWorkflowId}
                  >
                    Create Workflow
                  </Button>
                  {currentWorkflowId && (
                    <Text type="success">
                      <CheckCircleOutlined /> Workflow created: {currentWorkflowId}
                    </Text>
                  )}
                </Space>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        {/* Control Panel */}
        <Col xs={24} lg={8}>
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            {/* Workflow Status */}
            <Card title="Workflow Status" size="small">
              {workflowStatus ? (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <div>
                    <Text strong>Status: </Text>
                    <Tag color={getStatusColor(workflowStatus.status)} icon={getStatusIcon(workflowStatus.status)}>
                      {workflowStatus.status}
                    </Tag>
                  </div>
                  {workflowStatus.nifi_status && (
                    <div>
                      <Text strong>NiFi Status: </Text>
                      <Tag color={getStatusColor(workflowStatus.nifi_status)}>
                        {workflowStatus.nifi_status}
                      </Tag>
                    </div>
                  )}
                  <Button 
                    size="small" 
                    icon={<EyeOutlined />}
                    onClick={() => setShowStatusModal(true)}
                  >
                    View Details
                  </Button>
                </Space>
              ) : (
                <Text type="secondary">No workflow status available</Text>
              )}
            </Card>

            {/* Workflow Controls */}
            <Card title="Workflow Controls" size="small">
              <Space direction="vertical" style={{ width: '100%' }}>
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  onClick={handleExecuteWorkflow}
                  loading={executing}
                  disabled={!currentWorkflowId}
                  block
                >
                  Start Workflow
                </Button>
                <Button
                  icon={<StopOutlined />}
                  onClick={handleStopWorkflow}
                  disabled={!currentWorkflowId || workflowStatus?.status !== 'RUNNING'}
                  block
                >
                  Stop Workflow
                </Button>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={() => pollWorkflowStatus()}
                  disabled={!currentWorkflowId}
                  block
                >
                  Refresh Status
                </Button>
              </Space>
            </Card>

            {/* Quick Test */}
            <Card title="Quick Test" size="small">
              <Space direction="vertical" style={{ width: '100%' }}>
                <Upload {...uploadProps}>
                  <Button icon={<UploadOutlined />} block>
                    Upload Test File
                  </Button>
                </Upload>
                {fileName && (
                  <Alert
                    message={`File loaded: ${fileName}`}
                    type="success"
                    showIcon
                    closable
                  />
                )}
                <TextArea
                  placeholder="Or paste EDI content here for testing..."
                  rows={4}
                  value={fileContent}
                  onChange={(e) => setFileContent(e.target.value)}
                />
                <Button 
                  type="dashed" 
                  block
                  disabled={!fileContent || !currentWorkflowId}
                >
                  Process Test Content
                </Button>
              </Space>
            </Card>
          </Space>
        </Col>
      </Row>

      {/* Status Details Modal */}
      <Modal
        title="Workflow Status Details"
        open={showStatusModal}
        onCancel={() => setShowStatusModal(false)}
        footer={[
          <Button key="close" onClick={() => setShowStatusModal(false)}>
            Close
          </Button>
        ]}
        width={600}
      >
        {workflowStatus && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="Workflow ID">{workflowStatus.workflow_id}</Descriptions.Item>
            <Descriptions.Item label="Status">
              <Tag color={getStatusColor(workflowStatus.status)} icon={getStatusIcon(workflowStatus.status)}>
                {workflowStatus.status}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="NiFi Status">
              {workflowStatus.nifi_status ? (
                <Tag color={getStatusColor(workflowStatus.nifi_status)}>
                  {workflowStatus.nifi_status}
                </Tag>
              ) : 'N/A'}
            </Descriptions.Item>
            <Descriptions.Item label="Deployment Status">
              {workflowStatus.deployment_status || 'N/A'}
            </Descriptions.Item>
            <Descriptions.Item label="Health Check">
              {workflowStatus.health_check ? (
                <div>
                  <Tag color={workflowStatus.health_check.status === 'healthy' ? 'green' : 'red'}>
                    {workflowStatus.health_check.status}
                  </Tag>
                  {workflowStatus.health_check.issues?.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <Text strong>Issues:</Text>
                      <ul>
                        {workflowStatus.health_check.issues.map((issue, index) => (
                          <li key={index}>{issue}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : 'N/A'}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
};

export default EdiBatchProcessor;