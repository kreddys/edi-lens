import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Card, Space, Typography } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

/**
 * FlowEditor - Professional flow editing interface
 * Will be implemented to provide flow editing capabilities
 */
const FlowEditor: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();

    const handleBack = () => {
        navigate(`/flows/${id}`);
    };

    return (
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            <div style={{ marginBottom: 24 }}>
                <Space>
                    <Button 
                        icon={<ArrowLeftOutlined />} 
                        onClick={handleBack}
                    >
                        Back to Flow Details
                    </Button>
                    <Title level={2} style={{ margin: 0 }}>Edit Flow {id}</Title>
                </Space>
            </div>

            <Card>
                <div style={{ textAlign: 'center', padding: '60px 20px' }}>
                    <Title level={3}>Flow Editor</Title>
                    <Text type="secondary">
                        Advanced flow editing capabilities will be implemented here.
                        This will include visual flow designer, parameter editing, and version management.
                    </Text>
                </div>
            </Card>
        </div>
    );
};

export default FlowEditor;