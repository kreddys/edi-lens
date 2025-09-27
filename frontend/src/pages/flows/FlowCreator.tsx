import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
    Card, 
    Button, 
    Steps, 
    Typography, 
    Row, 
    Col, 
    List, 
    Input, 
    Form, 
    Select, 
    Space,
    Spin,
    notification,
    Tag,
    Descriptions,
    Alert
} from 'antd';
import { 
    ArrowLeftOutlined, 
    PlusOutlined, 
    FileTextOutlined, 
    RocketOutlined,
    ExclamationCircleOutlined
} from '@ant-design/icons';
import { flowAPI } from '../../providers/data';

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;

interface Template {
    id: string;
    name: string;
    description: string;
    category: string;
    tags: string[];
    parameters?: Record<string, any>;
}

interface Bucket {
    identifier: string;
    name: string;
    description: string;
}

/**
 * FlowCreator - Professional flow creation workflow with integrated template selection
 * Implements a step-by-step wizard for creating flows from templates
 */
const FlowCreator: React.FC = () => {
    const navigate = useNavigate();
    const [form] = Form.useForm();
    
    // Wizard state
    const [currentStep, setCurrentStep] = useState(0);
    const [loading, setLoading] = useState(false);
    
    // Data state
    const [templates, setTemplates] = useState<Template[]>([]);
    const [buckets, setBuckets] = useState<Bucket[]>([]);
    const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
    
    // Form data
    const [flowData, setFlowData] = useState({
        name: '',
        description: '',
        bucketId: '',
        parameters: {} as Record<string, any>
    });

    // Load initial data
    useEffect(() => {
        loadTemplates();
        loadBuckets();
    }, []);

    const loadTemplates = async () => {
        try {
            setLoading(true);
            const response = await flowAPI.listTemplates();
            setTemplates(response.templates || []);
        } catch (error) {
            console.error('Error loading templates:', error);
            notification.error({
                message: 'Error',
                description: 'Failed to load templates'
            });
        } finally {
            setLoading(false);
        }
    };

    const loadBuckets = async () => {
        try {
            const response = await flowAPI.listBuckets();
            setBuckets(response.buckets || []);
        } catch (error) {
            console.error('Error loading buckets:', error);
        }
    };

    const loadTemplateDetails = async (templateId: string) => {
        try {
            setLoading(true);
            await flowAPI.getTemplate(templateId, true);
            // Template details loaded successfully
        } catch (error) {
            console.error('Error loading template details:', error);
            notification.error({
                message: 'Error',
                description: 'Failed to load template details'
            });
        } finally {
            setLoading(false);
        }
    };

    const handleTemplateSelect = async (template: Template) => {
        setSelectedTemplate(template);
        await loadTemplateDetails(template.id);
        setCurrentStep(1);
    };

    const handleFlowDetailsSubmit = (values: any) => {
        setFlowData({
            ...flowData,
            name: values.name,
            description: values.description || '',
            bucketId: values.bucketId
        });
        setCurrentStep(2);
    };

    const handleParametersSubmit = (values: any) => {
        setFlowData({
            ...flowData,
            parameters: values
        });
        setCurrentStep(3);
    };

    const handleCreateFlow = async () => {
        if (!selectedTemplate) return;

        try {
            setLoading(true);
            
            const flowDefinition = {
                name: flowData.name,
                description: flowData.description,
                bucket_id: flowData.bucketId,
                template_id: selectedTemplate.id,
                parameters: flowData.parameters
            };

            const result = await flowAPI.createFlow(flowDefinition);
            
            notification.success({
                message: 'Success',
                description: 'Flow created successfully!'
            });

            // Navigate to the new flow
            navigate(`/flows/${result.id}`);
            
        } catch (error: any) {
            console.error('Error creating flow:', error);
            notification.error({
                message: 'Error',
                description: error.message || 'Failed to create flow'
            });
        } finally {
            setLoading(false);
        }
    };

    const steps = [
        {
            title: 'Select Template',
            icon: <FileTextOutlined />,
        },
        {
            title: 'Flow Details',
            icon: <PlusOutlined />,
        },
        {
            title: 'Configure Parameters',
            icon: <ExclamationCircleOutlined />,
        },
        {
            title: 'Review & Create',
            icon: <RocketOutlined />,
        },
    ];

    const renderTemplateSelection = () => (
        <Card title="Choose a Template" className="template-selection">
            <Spin spinning={loading}>
                <List
                    grid={{ gutter: 16, xs: 1, sm: 2, md: 3, lg: 3 }}
                    dataSource={templates}
                    renderItem={(template) => (
                        <List.Item>
                            <Card
                                hoverable
                                size="small"
                                onClick={() => handleTemplateSelect(template)}
                                actions={[
                                    <Button 
                                        type="primary" 
                                        size="small"
                                        onClick={() => handleTemplateSelect(template)}
                                    >
                                        Select
                                    </Button>
                                ]}
                            >
                                <Card.Meta
                                    title={template.name}
                                    description={
                                        <div>
                                            <Text type="secondary">{template.description}</Text>
                                            <div style={{ marginTop: 8 }}>
                                                <Tag color="blue">{template.category}</Tag>
                                                {template.tags?.map(tag => (
                                                    <Tag key={tag}>{tag}</Tag>
                                                ))}
                                            </div>
                                        </div>
                                    }
                                />
                            </Card>
                        </List.Item>
                    )}
                />
            </Spin>
        </Card>
    );

    const renderFlowDetails = () => (
        <Card title="Flow Information">
            <Form
                form={form}
                layout="vertical"
                onFinish={handleFlowDetailsSubmit}
                initialValues={{
                    name: selectedTemplate?.name ? `${selectedTemplate.name} Flow` : '',
                    description: selectedTemplate?.description || ''
                }}
            >
                <Row gutter={16}>
                    <Col span={12}>
                        <Form.Item
                            name="name"
                            label="Flow Name"
                            rules={[{ required: true, message: 'Please enter flow name' }]}
                        >
                            <Input placeholder="Enter flow name" />
                        </Form.Item>
                    </Col>
                    <Col span={12}>
                        <Form.Item
                            name="bucketId"
                            label="Storage Bucket"
                            rules={[{ required: true, message: 'Please select a bucket' }]}
                        >
                            <Select placeholder="Select bucket">
                                {buckets.map(bucket => (
                                    <Option key={bucket.identifier} value={bucket.identifier}>
                                        {bucket.name}
                                    </Option>
                                ))}
                            </Select>
                        </Form.Item>
                    </Col>
                </Row>
                <Form.Item name="description" label="Description">
                    <TextArea rows={3} placeholder="Enter flow description" />
                </Form.Item>
                <Form.Item>
                    <Space>
                        <Button onClick={() => setCurrentStep(0)}>Back</Button>
                        <Button type="primary" htmlType="submit">Next</Button>
                    </Space>
                </Form.Item>
            </Form>
        </Card>
    );

    const renderParameterConfiguration = () => (
        <Card title="Configure Parameters">
            <Alert
                message="Template Parameters"
                description="Configure the parameters required by this template"
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
            />
            {/* Parameter configuration would go here */}
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
                <Text type="secondary">Parameter configuration will be implemented based on template requirements</Text>
            </div>
            <Space>
                <Button onClick={() => setCurrentStep(1)}>Back</Button>
                <Button type="primary" onClick={() => handleParametersSubmit({})}>Next</Button>
            </Space>
        </Card>
    );

    const renderReviewAndCreate = () => (
        <Card title="Review Flow Configuration">
            <Descriptions column={1} bordered>
                <Descriptions.Item label="Template">
                    {selectedTemplate?.name}
                </Descriptions.Item>
                <Descriptions.Item label="Flow Name">
                    {flowData.name}
                </Descriptions.Item>
                <Descriptions.Item label="Description">
                    {flowData.description || 'No description'}
                </Descriptions.Item>
                <Descriptions.Item label="Storage Bucket">
                    {buckets.find(b => b.identifier === flowData.bucketId)?.name || flowData.bucketId}
                </Descriptions.Item>
            </Descriptions>
            
            <div style={{ marginTop: 16 }}>
                <Space>
                    <Button onClick={() => setCurrentStep(2)}>Back</Button>
                    <Button 
                        type="primary" 
                        icon={<RocketOutlined />}
                        loading={loading}
                        onClick={handleCreateFlow}
                    >
                        Create Flow
                    </Button>
                </Space>
            </div>
        </Card>
    );

    const renderCurrentStep = () => {
        switch (currentStep) {
            case 0:
                return renderTemplateSelection();
            case 1:
                return renderFlowDetails();
            case 2:
                return renderParameterConfiguration();
            case 3:
                return renderReviewAndCreate();
            default:
                return renderTemplateSelection();
        }
    };

    return (
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            {/* Header */}
            <div style={{ marginBottom: 24 }}>
                <Space>
                    <Button 
                        icon={<ArrowLeftOutlined />} 
                        onClick={() => navigate('/flows')}
                    >
                        Back to Flows
                    </Button>
                    <Title level={2} style={{ margin: 0 }}>Create New Flow</Title>
                </Space>
            </div>

            {/* Progress Steps */}
            <Card style={{ marginBottom: 24 }}>
                <Steps current={currentStep} items={steps} />
            </Card>

            {/* Step Content */}
            {renderCurrentStep()}
        </div>
    );
};

export default FlowCreator;