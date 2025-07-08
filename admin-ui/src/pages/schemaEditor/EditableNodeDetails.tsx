import React, { useEffect } from "react";
import { Form, Input, Select, InputNumber, Typography, Alert, Card } from "antd";
import type { FormInstance } from 'antd';

const { Title } = Typography;

interface EditableNodeDetailsProps {
    form: FormInstance;
    selectedNode: any;
    schemaContent: any;
    onValuesChange: (changedValues: any, allValues: any) => void;
    isShared: boolean;
}

export const EditableNodeDetails: React.FC<EditableNodeDetailsProps> = ({
    form,
    selectedNode,
    schemaContent,
    onValuesChange,
    isShared,
}) => {
    useEffect(() => {
        if (selectedNode) {
            form.setFieldsValue({
                ...selectedNode,
                ...schemaContent.segmentDefinitions[selectedNode.xid],
            });
        } else {
            form.resetFields();
        }
    }, [selectedNode, schemaContent, form]);

    if (!selectedNode) return null;

    const segmentDefinition = schemaContent.segmentDefinitions[selectedNode.xid];

    return (
        <Form
            form={form}
            layout="vertical"
            onValuesChange={onValuesChange}
            key={selectedNode.key}
        >
            <Title level={5}>Edit Node: {selectedNode.name} ({selectedNode.xid})</Title>
            <Card title="Structure Properties" size="small" style={{ marginBottom: 16 }}>
                <Form.Item name="name" label="Display Name (in tree)">
                    <Input />
                </Form.Item>
                <Form.Item name="usage" label="Usage">
                    <Select
                        options={[
                            { value: "R", label: "Required" },
                            { value: "S", label: "Situational" },
                            { value: "N", label: "Not Used" },
                        ]}
                    />
                </Form.Item>

                {selectedNode.type === "loop" && (
                    <Form.Item name="repeat" label="Repeat Count">
                        <Input placeholder="e.g., >1, 99" />
                    </Form.Item>
                )}

                {selectedNode.type === "segment" && (
                    <Form.Item name="max_use" label="Max Use">
                        <InputNumber min={0} style={{ width: '100%' }} />
                    </Form.Item>
                )}
            </Card>

            {selectedNode.type === "segment" && segmentDefinition && (
                <Card title="Segment Definition Properties" size="small">
                    {isShared && (
                        // --- FIX: Removed description to make it single-line ---
                        <Alert 
                            message="You are editing a shared segment definition."
                            type="info" 
                            showIcon
                            style={{ marginBottom: 16 }}
                        />
                    )}
                    <Form.Item name="name" label="Segment Definition Name">
                        <Input />
                    </Form.Item>
                </Card>
            )}

            {selectedNode.type === "segment" && !segmentDefinition && (
                 <Alert 
                    message="Unlinked Segment"
                    description="This segment is not linked to a definition."
                    type="warning" 
                    showIcon 
                />
            )}
        </Form>
    );
};