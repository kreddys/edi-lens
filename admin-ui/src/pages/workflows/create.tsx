import React from "react";
import {
  useSelect,
  useCreate,
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

const { Title, Text } = Typography;

export const WorkflowCreate: React.FC = () => {
  const [form] = Form.useForm();
  const { list, show } = useNavigation();
  const { mutate: createWorkflow, isLoading } = useCreate();
  const { notification } = App.useApp();
  
  const [templateConfig, setTemplateConfig] = React.useState<any>(null);
  const [loadingTemplate, setLoadingTemplate] = React.useState(false);

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
      
      // Use data provider's getOne method
      const result = await dataProvider().custom!({
        url: `/workflow-templates/${encodedTemplateId}`,
        method: "get"
      });
      
      if (result?.data) {
        setTemplateConfig(result.data);
        
        // Set default configuration values
        const defaultConfig: Record<string, any> = {};
        if (result.data.default_configuration) {
          Object.keys(result.data.default_configuration).forEach(key => {
            defaultConfig[key] = result.data.default_configuration[key];
          });
        }
        
        form.setFieldsValue({
          configuration: defaultConfig
        });
      }
    } catch (error: any) {
      notification.error({
        message: "Error",
        description: "Failed to load template configuration"
      });
      console.error("Template config error:", error);
    } finally {
      setLoadingTemplate(false);
    }
  };

  const handleTemplateChange = (templateId: string) => {
    form.setFieldsValue({ configuration: {} });
    setTemplateConfig(null);
    loadTemplateConfig(templateId);
  };

  const onFinish = async (values: any) => {
    try {
      const selectedTenant = localStorage.getItem('selected_tenant');
      if (!selectedTenant) {
        notification.error({
          message: "Error",
          description: "No tenant selected. Please select a tenant first."
        });
        return;
      }

      const workflowData = {
        ...values,
        tenant_id: selectedTenant,
        configuration: values.configuration || {}
      };

      createWorkflow({
        resource: "workflows",
        values: workflowData
      }, {
        onSuccess: (data) => {
          notification.success({
            message: "Success",
            description: "Workflow created successfully"
          });
          // Navigate to the newly created workflow
          show("workflows", data?.data?.workflow_id);
        },
        onError: (error: any) => {
          notification.error({
            message: "Error",
            description: error?.message || "Failed to create workflow"
          });
        }
      });
    } catch (error: any) {
      notification.error({
        message: "Error",
        description: error?.message || "Failed to create workflow"
      });
    }
  };

  return (
    <div>
      <h1>Create Workflow</h1>
      <Form
        form={form}
        layout="vertical"
        onFinish={onFinish}
        initialValues={{
          configuration: {}
        }}
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
                  onChange={handleTemplateChange}
                  showSearch
                  optionFilterProp="children"
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
            <Card title="Template Information" size="small">
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
                <Text type="secondary">Select a template to view its information</Text>
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
                  Create Workflow
                </Button>
                <Button 
                  onClick={() => list("workflows")}
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