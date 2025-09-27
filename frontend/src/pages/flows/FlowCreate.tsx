import React, { useState, useEffect } from "react";
import { Create, useForm } from "@refinedev/antd";
import { useGo } from "@refinedev/core";
import { Form, Input, Button, Select, Steps, Card, List as AntList, Tag, Typography, Space, Modal, message, Divider } from "antd";
import { FileTextOutlined, PlusOutlined, RocketOutlined } from "@ant-design/icons";
import { flowAPI } from "../../providers/data";

const { TextArea } = Input;
const { Text } = Typography;

interface Template {
    id: string;
    name: string;
    description: string;
    category: string;
    tags: string[];
    parameters?: Record<string, any>;
}

interface Bucket {
    id: string;
    name: string;
    description: string;
    allow_public_read: boolean;
    created_at: string;
    updated_at: string | null;
    flow_count: number;
    permissions: {
        canDelete: boolean;
        canRead: boolean;
        canWrite: boolean;
    };
    revision: {
        version: number;
    };
}

export const FlowCreate: React.FC = () => {
    const go = useGo();
    const { formProps } = useForm({
        action: "create",
        resource: "flows",
        redirect: false, // Prevent default redirect  
        onMutationSuccess: () => {
            // This won't be called since we're handling API calls manually
            message.success('Flow created successfully!');
        }
    });
    
    // Step wizard state
    const [currentStep, setCurrentStep] = useState(0);
    const [templates, setTemplates] = useState<Template[]>([]);
    const [buckets, setBuckets] = useState<Bucket[]>([]);
    const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
    const [loading, setLoading] = useState(false);
    
    // Form data state
    const [flowFormData, setFlowFormData] = useState<{
        name: string;
        description?: string;
        bucket_id: string;
    } | null>(null);
    
    // Bucket creation modal state
    const [createBucketModalOpen, setCreateBucketModalOpen] = useState(false);
    const [bucketForm] = Form.useForm();

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
        } finally {
            setLoading(false);
        }
    };

    const loadBuckets = async () => {
        try {
            const response = await flowAPI.listBuckets();
            setBuckets(response || []);
        } catch (error) {
            console.error('Error loading buckets:', error);
        }
    };

    const handleCreateFlow = async () => {
        try {
            setLoading(true);
            
            console.log('Form data:', flowFormData); // Debug log
            console.log('Selected template:', selectedTemplate); // Debug log
            
            if (!selectedTemplate) {
                message.error('Please select a template');
                return;
            }
            
            if (!flowFormData?.bucket_id) {
                message.error('Please select a bucket');
                console.log('Available flow form data:', flowFormData); // Debug log
                return;
            }
            
            // Prepare flow data
            const flowData = {
                name: flowFormData.name,
                description: flowFormData.description || '',
                bucket_id: flowFormData.bucket_id,
                parent_group_id: 'root',
                definition: (selectedTemplate as any).definition || null,
                parameters: (selectedTemplate as any).parameters || {}
            };
            
            // Create the flow using the API
            await flowAPI.createFlow(flowData);
            
            message.success(`Flow "${flowFormData.name}" created successfully!`);
            
            // Reset form state to prevent "unsaved changes" warning
            formProps.form?.resetFields();
            setFlowFormData(null);
            setSelectedTemplate(null);
            setCurrentStep(0);
            
            // Navigate back to flows list after successful creation
            setTimeout(() => {
                go({
                    to: { resource: 'flows', action: 'list' },
                    type: 'replace' // Use replace to avoid back button issues
                });
            }, 1000); // Small delay to show success message
            
        } catch (error) {
            console.error('Error creating flow:', error);
            message.error('Failed to create flow. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const handleCreateBucket = async (values: { name: string; description?: string }) => {
        try {
            setLoading(true);
            const newBucket = await flowAPI.createBucket({
                name: values.name,
                description: values.description
            });
            
            // Refresh bucket list
            await loadBuckets();
            
            // Close modal and reset form
            setCreateBucketModalOpen(false);
            bucketForm.resetFields();
            
            // Auto-select the new bucket in the main form
            formProps.form?.setFieldValue('bucket_id', newBucket.id);
            
            message.success(`Bucket "${values.name}" created successfully!`);
        } catch (error) {
            console.error('Error creating bucket:', error);
            message.error('Failed to create bucket. Please try again.');
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
            title: 'Review & Create',
            icon: <RocketOutlined />,
        },
    ];

    const renderTemplateSelection = () => (
        <Card title="Select Flow Template">
            <AntList
                loading={loading}
                grid={{ gutter: 16, column: 1 }}
                dataSource={templates}
                renderItem={(template: Template) => (
                    <AntList.Item>
                        <Card
                            hoverable
                            onClick={() => {
                                setSelectedTemplate(template);
                                setCurrentStep(1);
                            }}
                            style={{
                                border: selectedTemplate?.id === template.id ? '2px solid #1890ff' : '1px solid #d9d9d9'
                            }}
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
                    </AntList.Item>
                )}
            />
        </Card>
    );

    const handleFormSubmit = (values: any) => {
        console.log('Form submitted with values:', values); // Debug log
        setFlowFormData(values);
        setCurrentStep(2);
    };

    const renderFlowForm = () => (
        <Form {...formProps} layout="vertical" onFinish={handleFormSubmit}>
            <Card title="Flow Configuration">
                <Form.Item
                    label="Flow Name"
                    name="name"
                    rules={[{ required: true, message: 'Please enter a flow name' }]}
                >
                    <Input placeholder="Enter flow name" />
                </Form.Item>
                
                <Form.Item
                    label="Description"
                    name="description"
                >
                    <TextArea rows={3} placeholder="Enter flow description" />
                </Form.Item>
                
                <Form.Item
                    label="Storage Bucket"
                    name="bucket_id"
                    rules={[{ required: true, message: 'Please select a bucket' }]}
                >
                    <Select 
                        placeholder={buckets.length === 0 ? "No buckets available - Create one below" : "Select bucket"}
                        optionLabelProp="label"
                        dropdownRender={(menu) => (
                            <>
                                {menu}
                                <Divider style={{ margin: '8px 0' }} />
                                <Space style={{ padding: '0 8px 4px' }}>
                                    <Button 
                                        type="text" 
                                        icon={<PlusOutlined />}
                                        onClick={() => setCreateBucketModalOpen(true)}
                                    >
                                        Create New Bucket
                                    </Button>
                                </Space>
                            </>
                        )}
                    >
                        {buckets.map(bucket => (
                            <Select.Option key={bucket.id} value={bucket.id} label={bucket.name}>
                                <div>
                                    <div style={{ fontWeight: 500 }}>{bucket.name}</div>
                                    {bucket.description && (
                                        <div style={{ fontSize: '12px', color: '#666' }}>{bucket.description}</div>
                                    )}
                                </div>
                            </Select.Option>
                        ))}
                    </Select>
                </Form.Item>
            </Card>
            
            <Space style={{ marginTop: 16 }}>
                <Button onClick={() => setCurrentStep(0)}>Back</Button>
                <Button type="primary" htmlType="submit">Next</Button>
            </Space>
        </Form>
    );

    const renderReview = () => {
        const selectedBucket = buckets.find(bucket => bucket.id === flowFormData?.bucket_id);
        
        return (
            <Card title="Review Flow Configuration">
                <div style={{ marginBottom: 16 }}>
                    <Text strong>Template: </Text>
                    <Text>{selectedTemplate?.name}</Text>
                </div>
                <div style={{ marginBottom: 16 }}>
                    <Text strong>Flow Name: </Text>
                    <Text>{flowFormData?.name || 'Not set'}</Text>
                </div>
                <div style={{ marginBottom: 16 }}>
                    <Text strong>Description: </Text>
                    <Text>{flowFormData?.description || 'None'}</Text>
                </div>
                <div style={{ marginBottom: 16 }}>
                    <Text strong>Storage Bucket: </Text>
                    <Text>{selectedBucket?.name || 'Not selected'}</Text>
                </div>
                <Space>
                    <Button onClick={() => setCurrentStep(1)}>Back</Button>
                    <Button type="primary" loading={loading} onClick={handleCreateFlow}>
                        Create Flow
                    </Button>
                </Space>
            </Card>
        );
    };

    const renderCurrentStep = () => {
        switch (currentStep) {
            case 0:
                return renderTemplateSelection();
            case 1:
                return renderFlowForm();
            case 2:
                return renderReview();
            default:
                return renderTemplateSelection();
        }
    };

    return (
        <Create
            title="Create New Flow"
            saveButtonProps={{ style: { display: 'none' } }} // Hide default save button
        >
            <Steps current={currentStep} items={steps} style={{ marginBottom: 24 }} />
            {renderCurrentStep()}
            
            {/* Bucket Creation Modal */}
            <Modal
                title="Create New Bucket"
                open={createBucketModalOpen}
                onCancel={() => {
                    setCreateBucketModalOpen(false);
                    bucketForm.resetFields();
                }}
                footer={null}
                destroyOnClose
            >
                <Form
                    form={bucketForm}
                    layout="vertical"
                    onFinish={handleCreateBucket}
                >
                    <Form.Item
                        label="Bucket Name"
                        name="name"
                        rules={[
                            { required: true, message: 'Please enter a bucket name' },
                            { 
                                pattern: /^[a-zA-Z0-9][a-zA-Z0-9\-_]*[a-zA-Z0-9]$|^[a-zA-Z0-9]$/, 
                                message: 'Name must be alphanumeric with optional hyphens/underscores (not at start/end)' 
                            }
                        ]}
                    >
                        <Input placeholder="Enter bucket name" />
                    </Form.Item>
                    
                    <Form.Item
                        label="Description (Optional)"
                        name="description"
                    >
                        <Input.TextArea 
                            placeholder="Enter bucket description" 
                            rows={3}
                        />
                    </Form.Item>
                    
                    <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
                        <Space>
                            <Button onClick={() => {
                                setCreateBucketModalOpen(false);
                                bucketForm.resetFields();
                            }}>
                                Cancel
                            </Button>
                            <Button 
                                type="primary" 
                                htmlType="submit"
                                loading={loading}
                                icon={<PlusOutlined />}
                            >
                                Create Bucket
                            </Button>
                        </Space>
                    </Form.Item>
                </Form>
            </Modal>
        </Create>
    );
};