import React, { useEffect } from "react";
import { Form, Input, Select, InputNumber, Typography, Alert, Card, Button } from "antd";
import type { FormInstance } from 'antd';

const { Title } = Typography;

interface EditableNodeDetailsProps {
    structureForm: FormInstance;
    definitionForm: FormInstance;
    selectedNode: any;
    schemaContent: any;
    onStructureValuesChange: (changedValues: any) => void;
    onDefinitionValuesChange: (changedValues: any) => void;
    onSpecialize: () => void;
    isShared: boolean;
}

export const EditableNodeDetails: React.FC<EditableNodeDetailsProps> = ({
    structureForm,
    definitionForm,
    selectedNode,
    schemaContent,
    onStructureValuesChange,
    onDefinitionValuesChange,
    onSpecialize,
    isShared,
}) => {
    
    const definitionId = selectedNode.definitionId || selectedNode.xid;
    const segmentDefinition = schemaContent.segmentDefinitions[definitionId];

    useEffect(() => {
        if (selectedNode) {
            structureForm.setFieldsValue(selectedNode);
            if (segmentDefinition) {
                definitionForm.setFieldsValue(segmentDefinition);
            }
        } else {
            structureForm.resetFields();
            definitionForm.resetFields();
        }
    }, [selectedNode, segmentDefinition, structureForm, definitionForm]);

    if (!selectedNode) return null;

    return (
        <div>
            <Title level={5}>Edit Node: {selectedNode.name} ({selectedNode.xid})</Title>
            
            <Form form={structureForm} layout="vertical" onValuesChange={onStructureValuesChange} key={`${selectedNode.key}-struct`}>
                <Card title="Structure Properties" size="small" style={{ marginBottom: 16 }}>
                    <Form.Item name="name" label="Display Name (in tree)"><Input /></Form.Item>
                    <Form.Item name="usage" label="Usage">
                        <Select options={[{ value: "R", label: "Required" }, { value: "S", label: "Situational" }, { value: "N", label: "Not Used" }]}/>
                    </Form.Item>
                    {selectedNode.type === "loop" && <Form.Item name="repeat" label="Repeat Count"><Input placeholder="e.g., >1, 99" /></Form.Item>}
                    {selectedNode.type === "segment" && <Form.Item name="max_use" label="Max Use"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>}
                </Card>
            </Form>

            {selectedNode.type === "segment" && (
                <Form form={definitionForm} layout="vertical" onValuesChange={onDefinitionValuesChange} key={`${selectedNode.key}-def`}>
                    <Card title="Segment Definition Properties" size="small">
                        {segmentDefinition ? (
                            <>
                                {isShared && (
                                    <Alert
                                        message="This is a shared definition."
                                        description={<Button type="link" onClick={onSpecialize} style={{padding:0}}>Create a specialized definition to edit independently.</Button>}
                                        type="info"
                                        showIcon
                                        style={{ marginBottom: 16 }}
                                    />
                                )}
                                <Form.Item name="name" label="Definition Name">
                                    <Input disabled={isShared} />
                                </Form.Item>
                            </>
                        ) : (
                            <Alert message="Unlinked Segment" type="warning" showIcon />
                        )}
                    </Card>
                </Form>
            )}
        </div>
    );
};