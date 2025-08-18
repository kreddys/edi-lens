# NiFi Workflows - UI Development Guide

*Complete guide for developing and integrating the NiFi workflow user interface*

## 🎯 **Overview**

This guide covers the complete UI implementation for NiFi workflow management, including component development, backend integration, and user experience patterns.

## 🏗️ **UI Architecture**

### **Page Structure**
The NiFi workflow UI is integrated into the main EDI Lens admin interface with the following pages:

```
/workflow-templates     # Template management
├── /                  # List all templates
├── /create           # Create new template
├── /edit/:id         # Edit existing template
└── /show/:id         # View template details

/workflows             # Workflow management  
├── /                 # List all workflows
├── /create          # Create new workflow
├── /edit/:id        # Edit existing workflow
└── /show/:id        # View workflow details + execution
```

### **Component Hierarchy**
```
pages/
├── workflowTemplates/
│   ├── list.tsx           # Template listing with filters
│   ├── create.tsx         # Template creation form
│   ├── edit.tsx           # Template editing
│   └── show.tsx           # Template details view
├── workflows/
│   ├── list.tsx           # Workflow listing with actions
│   ├── create.tsx         # Workflow creation wizard
│   ├── edit.tsx           # Workflow configuration
│   └── show.tsx           # Workflow details + execution
└── components/workflow/
    ├── WorkflowExecute.tsx    # EDI processing interface
    ├── WorkflowControl.tsx    # Workflow state controls
    ├── StatusBadges.tsx       # Status indicators
    └── TemplateSelector.tsx   # Template selection
```

## 🧩 **Core Components**

### **1. WorkflowExecute Component**

Complete EDI processing interface with file upload and execution capabilities.

```typescript
// components/workflow/WorkflowExecute.tsx
interface WorkflowExecuteProps {
  workflowId: string;
}

export const WorkflowExecute: React.FC<WorkflowExecuteProps> = ({ workflowId }) => {
  const [ediContent, setEdiContent] = useState<string>("");
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState<ValidationResult | null>(null);
  
  // File upload handling
  const handleFileUpload = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      setEdiContent(e.target?.result as string);
    };
    reader.readAsText(file);
    return false; // Prevent auto upload
  };

  // Workflow execution
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
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <div style={{ padding: "24px" }}>
      <Title level={2}>Execute Workflow</Title>
      
      <Row gutter={[24, 24]}>
        {/* EDI Input Section */}
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
                <Button onClick={() => { setEdiContent(""); setExecutionResult(null); }}>
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
                {/* Execution Summary */}
                <Card size="small" style={{ marginBottom: 16 }}>
                  <Statistic
                    title="Processing Time"
                    value={executionResult.processing_time_ms}
                    suffix="ms"
                    valueStyle={{ color: '#1677ff' }}
                  />
                </Card>

                {/* Validation Results */}
                {executionResult.validation_results && (
                  <Table
                    dataSource={executionResult.validation_results}
                    columns={[
                      { title: 'Level', dataIndex: 'level', key: 'level' },
                      { title: 'Code', dataIndex: 'code', key: 'code' },
                      { title: 'Message', dataIndex: 'message', key: 'message' }
                    ]}
                    size="small"
                    pagination={false}
                  />
                )}

                {/* Download Results */}
                {executionResult.ta1_acknowledgment && (
                  <Button 
                    icon={<DownloadOutlined />}
                    onClick={() => downloadResponse(executionResult.ta1_acknowledgment!, 'ta1_ack.edi')}
                  >
                    Download TA1
                  </Button>
                )}
              </Space>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};
```

### **2. WorkflowControl Component**

Workflow state management controls for deploy, start, stop, restart operations.

```typescript
// components/workflow/WorkflowControl.tsx
interface WorkflowControlProps {
  workflowId: string;
  isDeployed: boolean;
  status: string;
  onActionComplete: () => void;
}

export const WorkflowControl: React.FC<WorkflowControlProps> = ({
  workflowId,
  isDeployed,
  status,
  onActionComplete
}) => {
  const { notification } = App.useApp();
  const dataProvider = useDataProvider();

  const handleAction = async (action: string) => {
    try {
      let endpoint = "";
      switch (action) {
        case "deploy":
          endpoint = `/workflows/${workflowId}/deploy`;
          break;
        case "undeploy":
          endpoint = `/workflows/${workflowId}/undeploy`;
          break;
        case "start":
        case "resume":
          endpoint = `/workflows/${workflowId}/resume`;
          break;
        case "stop":
        case "pause":
          endpoint = `/workflows/${workflowId}/pause`;
          break;
        case "restart":
          endpoint = `/workflows/${workflowId}/restart`;
          break;
        default:
          throw new Error("Invalid action");
      }

      await dataProvider().custom!({
        url: endpoint,
        method: "post"
      });

      notification.success({
        message: "Success",
        description: `Workflow ${action} completed successfully`
      });

      onActionComplete();
    } catch (error: any) {
      notification.error({
        message: "Action Failed",
        description: error.message || `Failed to ${action} workflow`
      });
    }
  };

  return (
    <Card title="⚙️ Workflow Controls" size="small">
      <Space wrap>
        {!isDeployed ? (
          <Button 
            type="primary"
            icon={<CloudUploadOutlined />}
            onClick={() => handleAction("deploy")}
          >
            Deploy
          </Button>
        ) : (
          <>
            {status === "RUNNING" ? (
              <Button 
                icon={<PauseCircleOutlined />}
                onClick={() => handleAction("pause")}
                title="Pause"
              >
                Pause
              </Button>
            ) : (
              <Button 
                icon={<PlayCircleOutlined />}
                onClick={() => handleAction("resume")}
                title="Resume"
              >
                Resume
              </Button>
            )}
            
            <Button 
              icon={<RedoOutlined />}
              onClick={() => handleAction("restart")}
              title="Restart"
            >
              Restart
            </Button>
            
            <Button 
              danger
              icon={<CloudDownloadOutlined />}
              onClick={() => handleAction("undeploy")}
              title="Undeploy"
            >
              Undeploy
            </Button>
          </>
        )}
      </Space>
    </Card>
  );
};
```

### **3. StatusBadges Component**

Reusable status indicators for templates and workflows.

```typescript
// components/workflow/StatusBadges.tsx
export const TemplateStatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const statusConfig: Record<string, { color: string; text: string }> = {
    ACTIVE: { color: "success", text: "Active" },
    DEPRECATED: { color: "warning", text: "Deprecated" },
    ARCHIVED: { color: "default", text: "Archived" },
  };
  
  const config = statusConfig[status] || { color: "default", text: status };
  return <Tag color={config.color}>{config.text}</Tag>;
};

export const WorkflowStatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const statusConfig: Record<string, { color: string; text: string }> = {
    ACTIVE: { color: "success", text: "Active" },
    PAUSED: { color: "warning", text: "Paused" },
    ERROR: { color: "error", text: "Error" },
    DELETED: { color: "default", text: "Deleted" },
  };
  
  const config = statusConfig[status] || { color: "default", text: status };
  return <Tag color={config.color}>{config.text}</Tag>;
};

export const DeploymentBadge: React.FC<{ isDeployed: boolean }> = ({ isDeployed }) => {
  if (isDeployed) {
    return <Tag color="green">Deployed</Tag>;
  }
  return <Tag color="default">Not Deployed</Tag>;
};
```

## 📋 **Page Implementations**

### **1. Workflow Templates List**

```typescript
// pages/workflowTemplates/list.tsx
export const WorkflowTemplateList: React.FC<IResourceComponentsProps> = () => {
  const { tableProps, tableQueryResult } = useTable<WorkflowTemplate, HttpError>({
    queryOptions: {
      onSuccess: (data) => {
        logger.log("Templates loaded:", data.data?.length);
      },
      onError: (error) => {
        logger.error("Error fetching templates:", error);
      }
    }
  });

  return (
    <List>
      <Table {...tableProps} rowKey="template_id">
        <Table.Column
          dataIndex="name"
          title="Name"
          render={(value, record: any) => (
            <Space direction="vertical" size={0}>
              <Text strong>{value}</Text>
              <Text type="secondary" style={{ fontSize: "12px" }}>
                {record.description}
              </Text>
            </Space>
          )}
        />
        <Table.Column
          dataIndex="category"
          title="Category"
          render={(value) => <CategoryBadge category={value} />}
        />
        <Table.Column
          dataIndex="status"
          title="Status"
          render={(value) => <TemplateStatusBadge status={value} />}
        />
        <Table.Column
          dataIndex="usage_count"
          title="Usage"
          render={(value) => <Text type="secondary">{value} workflows</Text>}
        />
        <Table.Column
          title="Actions"
          dataIndex="actions"
          render={(_, record: BaseRecord) => (
            <Space>
              <ShowButton hideText size="small" recordItemId={record.template_id} />
              <EditButton hideText size="small" recordItemId={record.template_id} />
            </Space>
          )}
        />
      </Table>
    </List>
  );
};
```

### **2. Workflow Creation**

```typescript
// pages/workflows/create.tsx
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

  // Load template configuration when template is selected
  const loadTemplateConfig = async (templateId: string) => {
    if (!templateId) return;
    
    setLoadingTemplate(true);
    try {
      const encodedTemplateId = encodeURIComponent(templateId);
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
                      <Text type="secondary">{templateConfig.description}</Text>
                    </div>
                  )}
                  <div>
                    <Text strong>Version:</Text><br />
                    <Tag>{templateConfig.version}</Tag>
                  </div>
                </Space>
              ) : (
                <Text type="secondary">Select a template to view information</Text>
              )}
            </Card>
          </Col>
        </Row>

        <div style={{ marginTop: 24 }}>
          <Space>
            <Button type="primary" htmlType="submit" loading={isLoading}>
              Create Workflow
            </Button>
            <Button onClick={() => list("workflows")}>
              Cancel
            </Button>
          </Space>
        </div>
      </Form>
    </div>
  );
};
```

## 🔗 **Backend Integration**

### **Data Provider Configuration**

```typescript
// providers/data.ts
export const dataProvider: DataProvider = {
  ...baseDataProvider,
  
  getList: async (params) => {
    // For workflows resource, add tenant_id as a query parameter
    if (params.resource === "workflows") {
      const selectedTenant = localStorage.getItem('selected_tenant');
      if (selectedTenant) {
        let url = `${import.meta.env.VITE_API_URL}/${params.resource}?tenant_id=${selectedTenant}`;
        
        // Add pagination parameters
        if (params.pagination) {
          const current = params.pagination.current || 1;
          const pageSize = params.pagination.pageSize || 10;
          const start = (current - 1) * pageSize;
          const end = start + pageSize;
          url += `&_start=${start}&_end=${end}`;
        }
        
        // Add sorting parameters
        if (params.sorters && params.sorters.length > 0) {
          const sortParam = params.sorters.map(sort => 
            `${sort.order === "desc" ? "-" : ""}${sort.field}`
          ).join(",");
          url += `&_sort=${sortParam}`;
        }
        
        // Add filter parameters
        if (params.filters && params.filters.length > 0) {
          params.filters.forEach(filter => {
            if (filter.operator !== "or" && filter.operator !== "and" && 'field' in filter) {
              if (filter.field !== "tenant_id") {
                url += `&${filter.field}=${filter.value}`;
              }
            }
          });
        }
        
        const response = await fetch(url, {
          headers: createAuthHeaders()
        });
        
        const data = await response.json();
        
        return {
          data: data.workflows || [],
          total: data.total || data.workflows?.length || 0
        };
      }
    }
    
    return baseDataProvider.getList(params);
  },
  
  // Custom workflow actions
  custom: async ({ url, method, payload, headers }) => {
    const response = await fetch(`${import.meta.env.VITE_API_URL}${url}`, {
      method: method.toUpperCase(),
      headers: {
        ...createAuthHeaders(),
        ...headers
      },
      body: payload ? JSON.stringify(payload) : undefined
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    return { data };
  }
};
```

### **Authentication Integration**

```typescript
// utils/auth.ts
export const createAuthHeaders = () => {
  const selectedTenant = localStorage.getItem('selected_tenant');
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json'
  };
  
  if (keycloak.authenticated && keycloak.token) {
    headers.Authorization = `Bearer ${keycloak.token}`;
  }
  
  if (selectedTenant) {
    headers['X-Tenant-ID'] = selectedTenant;
  }
  
  return headers;
};
```

## 🎨 **UI/UX Patterns**

### **Design Principles**
- **Consistent Layout**: All pages follow the same layout patterns
- **Progressive Disclosure**: Complex configuration revealed as needed
- **Clear Status Indicators**: Visual status communication throughout
- **Responsive Design**: Works on desktop and mobile devices
- **Error Handling**: Graceful error states and user feedback

### **Color Coding**
- **Green**: Active, deployed, successful states
- **Orange/Yellow**: Warning, paused, pending states  
- **Red**: Error, failed, stopped states
- **Blue**: Information, running, processing states
- **Gray**: Inactive, archived, disabled states

### **Interactive Elements**
- **Hover States**: Clear feedback on interactive elements
- **Loading States**: Spinners and progress indicators
- **Confirmation Dialogs**: For destructive actions
- **Tooltips**: Additional information and help text

## 🧪 **Testing Strategy**

### **Component Testing**
```typescript
// __tests__/ui/WorkflowExecute.test.tsx
describe('WorkflowExecute Component', () => {
  it('renders workflow execute interface correctly', () => {
    render(
      <TestWrapper dataProvider={mockDataProvider}>
        <AntdApp>
          <WorkflowExecute workflowId="test-workflow-123" />
        </AntdApp>
      </TestWrapper>
    );

    expect(screen.getByText('Execute Workflow')).toBeInTheDocument();
    expect(screen.getByText('📄 EDI Input')).toBeInTheDocument();
    expect(screen.getByText('📊 Execution Results')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/paste your edi content/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /execute workflow/i })).toBeInTheDocument();
  });

  it('handles EDI content input correctly', async () => {
    const user = userEvent.setup();
    
    render(
      <TestWrapper dataProvider={mockDataProvider}>
        <AntdApp>
          <WorkflowExecute workflowId="test-workflow-123" />
        </AntdApp>
      </TestWrapper>
    );

    const textarea = screen.getByPlaceholderText(/paste your edi content/i);
    const testEdiContent = 'ISA*00*TEST*EDI*CONTENT~';
    
    await user.type(textarea, testEdiContent);
    
    expect(textarea).toHaveValue(testEdiContent);
  });
});
```

### **Integration Testing**
```typescript
// __tests__/e2e/WorkflowIntegration.test.tsx
describe('Workflow Integration Tests', () => {
  it('completes full workflow creation and execution', async () => {
    // 1. Navigate to workflow creation
    // 2. Select template
    // 3. Configure parameters
    // 4. Create workflow
    // 5. Deploy workflow
    // 6. Execute with EDI content
    // 7. Verify results
  });
});
```

## 📚 **Best Practices**

### **Component Development**
- **Single Responsibility**: Each component has a clear, focused purpose
- **Prop Typing**: Full TypeScript interfaces for all props
- **Error Boundaries**: Graceful error handling and recovery
- **Performance**: React.memo and useMemo for optimization
- **Accessibility**: ARIA labels and keyboard navigation

### **State Management**
- **Local State**: Component-specific state using useState
- **Form State**: Ant Design Form for complex form management
- **Server State**: React Query for server state management
- **Global State**: Context API for shared application state

### **API Integration**
- **Error Handling**: Consistent error handling patterns
- **Loading States**: User feedback during async operations
- **Caching**: Appropriate caching strategies for performance
- **Optimistic Updates**: Immediate UI feedback where appropriate

### **Code Organization**
- **File Structure**: Logical grouping of related components
- **Import Organization**: Consistent import ordering and grouping
- **Naming Conventions**: Clear, descriptive naming throughout
- **Documentation**: Comprehensive component and function documentation

---

This guide provides a complete foundation for developing and maintaining the NiFi workflow UI components with consistent patterns, robust error handling, and excellent user experience.