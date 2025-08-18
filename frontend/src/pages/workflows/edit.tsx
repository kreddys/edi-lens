import React, { useEffect } from "react";
import {
  useSelect,
  useUpdate,
  useShow,
  useNavigation,
  useDataProvider
} from "@refinedev/core";
import {
  Form,
  Input,
  Select,
  Button,
  Card,
  Row,
  Col,
  Typography,
  Spin,
  Alert,
  Space,
  Divider,
  App
} from "antd";
import { useParams } from "react-router-dom";

const { Title, Text } = Typography;

export const WorkflowEdit: React.FC = () => {
  const [form] = Form.useForm();
  const { show } = useNavigation();
  const { id } = useParams();
  const { mutate: updateWorkflow, isLoading } = useUpdate();
  const { notification } = App.useApp();
  
  const [templateConfig, setTemplateConfig] = React.useState<any>(null);
  const [loadingTemplate, setLoadingTemplate] = React.useState(false);

  // Get workflow data
  const { queryResult } = useShow({
    resource: "workflows",
    id: id
  });
  const { isLoading: isWorkflowLoading } = queryResult;
  const workflow = queryResult?.data?.data;

  // Get available workflow templates
  const templateSelectResult = useSelect({
    resource: "workflow-templates",
    optionLabel: "name",
    optionValue: "template_id",
    filters: [
      {
        field: "status",
        operator: "eq",
        value: "ACTIVE"
      }
    ]
  });

  const dataProvider = useDataProvider();

  // Function to load template configuration
  const loadTemplateConfig = async (templateId: string) => {
    if (!templateId) return;
    
    setLoadingTemplate(true);
    try {
      // URL encode the template ID to handle special characters like dots
      const encodedTemplateId = encodeURIComponent(templateId);
      
      const result = await dataProvider().custom!({
        url: `/workflow-templates/${encodedTemplateId}`,
        method: "get"
      });
      
      if (result?.data) {
        setTemplateConfig(result.data);
      }
    } catch (error: any) {
      console.error("Template config error:", error);
      // Don't show notification for template config errors in edit mode
      // as this is not critical and the workflow can still be edited
    } finally {
      setLoadingTemplate(false);
    }
  };

  // Set form values when workflow data is loaded
  useEffect(() => {
    if (workflow) {
      form.setFieldsValue({
        name: workflow.name,
        description: workflow.description,
        template_id: workflow.template_id,
        tags: workflow.tags,
        configuration: workflow.configuration || {}
      });
      
      // Fetch template config for the current template
      loadTemplateConfig(workflow.template_id);
    }
  }, [workflow, form]);

  const onFinish = async (values: any) => {
    try {
      updateWorkflow({
        resource: "workflows",
        id: id,
        values: values
      }, {
        onSuccess: (_data) => {
          notification.success({
            message: "Success",
            description: "Workflow updated successfully"
          });
          // Navigate to the updated workflow
          show("workflows", id!);
        },
        onError: (error: any) => {
          notification.error({
            message: "Error",
            description: error?.message || "Failed to update workflow"
          });
        }
      });
    } catch (error: any) {
      notification.error({
        message: "Error",
        description: error?.message || "Failed to update workflow"
      });
    }
  };

  if (isWorkflowLoading) {
    return (
      <div style={{ textAlign: "center", padding: "50px" }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>
          <Text>Loading workflow...</Text>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1>Edit Workflow</h1>
      <Form
        form={form}
        layout="vertical"
        onFinish={onFinish}
      >
        <Row gutter={[24, 24]}>
          <Col xs={24} lg={16}>
            <Card title="Workflow Details" size="small">
              <Form.Item
                label="Name"
                name="name"
                rules={[{ required: true, message: "Please enter a workflow name" }]}
              >
                <Input placeholder="Enter workflow name" />
              </Form.Item>

              <Form.Item
                label="Description"
                name="description"
              >
                <Input.TextArea placeholder="Enter workflow description" rows={3} />
              </Form.Item>

              <Form.Item
                label="Template"
                name="template_id"
                rules={[{ required: true, message: "Please select a template" }]}
              >
                <Select
                  {...templateSelectResult}
                  placeholder="Select a workflow template"
                  showSearch
                  optionFilterProp="children"
                  disabled // Template shouldn't be changed after creation
                />
              </Form.Item>

              <Form.Item
                label="Tags"
                name="tags"
              >
                <Select
                  mode="tags"
                  placeholder="Add tags (optional)"
                  tokenSeparators={[","]}
                />
              </Form.Item>
            </Card>

            {loadingTemplate && (
              <div style={{ textAlign: "center", padding: "20px" }}>
                <Spin />
                <div style={{ marginTop: 10 }}>
                  <Text>Loading template configuration...</Text>
                </div>
              </div>
            )}

            {templateConfig && (
              <Card 
                title="Configuration" 
                size="small" 
                style={{ marginTop: 16 }}
                extra={
                  <Button 
                    type="link" 
                    onClick={() => {
                      // Reset to default configuration
                      const defaultConfig: Record<string, any> = {};
                      if (templateConfig.default_configuration) {
                        Object.keys(templateConfig.default_configuration).forEach(key => {
                          defaultConfig[key] = templateConfig.default_configuration[key];
                        });
                      }
                      form.setFieldsValue({ configuration: defaultConfig });
                    }}
                  >
                    Reset to Default
                  </Button>
                }
              >
                {templateConfig.documentation && (
                  <Alert
                    message="Template Documentation"
                    description={templateConfig.documentation}
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />
                )}

                {templateConfig.required_parameters && templateConfig.required_parameters.length > 0 && (
                  <>
                    <Title level={5}>Required Parameters</Title>
                    <div style={{ marginBottom: 16 }}>
                      {templateConfig.required_parameters.map((param: string) => (
                        <Form.Item
                          key={param}
                          label={param}
                          name={['configuration', param]}
                          rules={[{ required: true, message: `Please enter ${param}` }]}
                        >
                          <Input placeholder={`Enter ${param}`} />
                        </Form.Item>
                      ))}
                    </div>
                  </>
                )}

                {templateConfig.optional_parameters && templateConfig.optional_parameters.length > 0 && (
                  <>
                    <Divider orientation="left" plain>Optional Parameters</Divider>
                    <div>
                      {templateConfig.optional_parameters.map((param: string) => (
                        <Form.Item
                          key={param}
                          label={param}
                          name={['configuration', param]}
                        >
                          <Input placeholder={`Enter ${param} (optional)`} />
                        </Form.Item>
                      ))}
                    </div>
                  </>
                )}

                {(!templateConfig.required_parameters || templateConfig.required_parameters.length === 0) &&
                 (!templateConfig.optional_parameters || templateConfig.optional_parameters.length === 0) && (
                  <Text type="secondary">This template does not require any configuration parameters.</Text>
                )}
              </Card>
            )}
          </Col>

          <Col xs={24} lg={8}>
            <Card title="Workflow Information" size="small">
              {workflow && (
                <Space direction="vertical" style={{ width: "100%" }}>
                  <div>
                    <Text strong>Workflow ID:</Text><br />
                    <Text code>{workflow.workflow_id}</Text>
                  </div>
                  <div>
                    <Text strong>Status:</Text><br />
                    <Text>{workflow.status}</Text>
                  </div>
                  <div>
                    <Text strong>Deployment:</Text><br />
                    <Text>{workflow.is_deployed ? "Deployed" : "Not Deployed"}</Text>
                  </div>
                  {workflow.created_at && (
                    <div>
                      <Text strong>Created:</Text><br />
                      <Text>{new Date(workflow.created_at).toLocaleString()}</Text>
                    </div>
                  )}
                  {workflow.updated_at && (
                    <div>
                      <Text strong>Updated:</Text><br />
                      <Text>{new Date(workflow.updated_at).toLocaleString()}</Text>
                    </div>
                  )}
                </Space>
              )}
            </Card>

            <Card title="Template Information" size="small" style={{ marginTop: 16 }}>
              {templateConfig ? (
                <Space direction="vertical" style={{ width: "100%" }}>
                  <div>
                    <Text strong>Template:</Text><br />
                    <Text>{templateConfig.name}</Text>
                  </div>
                  <div>
                    <Text strong>Category:</Text><br />
                    <Text code>{templateConfig.category}</Text>
                  </div>
                  <div>
                    <Text strong>Scope:</Text><br />
                    <Text code>{templateConfig.scope}</Text>
                  </div>
                  {templateConfig.description && (
                    <div>
                      <Text strong>Description:</Text><br />
                      <Text>{templateConfig.description}</Text>
                    </div>
                  )}
                  <div>
                    <Text strong>Version:</Text><br />
                    <Text code>{templateConfig.version}</Text>
                  </div>
                </Space>
              ) : (
                <Text type="secondary">Loading template information...</Text>
              )}
            </Card>

            <Card title="Actions" size="small" style={{ marginTop: 16 }}>
              <Space direction="vertical" style={{ width: "100%" }}>
                <Button 
                  type="primary" 
                  htmlType="submit" 
                  loading={isLoading}
                  block
                >
                  Update Workflow
                </Button>
                <Button 
                  onClick={() => show("workflows", id!)}
                  block
                >
                  Cancel
                </Button>
              </Space>
            </Card>
          </Col>
        </Row>
      </Form>
    </div>
  );
};