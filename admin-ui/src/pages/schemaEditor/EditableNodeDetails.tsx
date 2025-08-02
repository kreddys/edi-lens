import React, { useMemo, useEffect } from "react";
import { Form, Input, Select, InputNumber, Typography, Alert, Card, Button, Descriptions, Tag, Divider, Space, notification, Table, Empty, Tooltip } from "antd";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import type { FormInstance } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { updateNodeByKey } from "./schemaEditorUtils.tsx";
import { BaseElement, ContextualDefinition, SegmentDefinition, CodeDefinition } from "./types";
import { SyntaxRuleDisplay } from "./SyntaxRuleDisplay";

const { Title, Text } = Typography;

interface EditableNodeDetailsProps {
    form: FormInstance;
    selectedNode: any;
    schemaContent: any;
    onUpdateSchema: (newSchemaContent: any) => void;
    isEditing: boolean;
}

const ElementDisplayTable: React.FC<{ elements: BaseElement[]; overrides?: { [key: string]: any } }> = ({ elements, overrides }) => {
    const columns: ColumnsType<BaseElement> = [
        { title: 'Seq', dataIndex: 'seq', key: 'seq', width: '10%' },
        { 
            title: 'Element ID', 
            dataIndex: 'xid', 
            key: 'xid', 
            width: '20%',
            render: (text, record) => (
                <Text strong={record.is_identifier}>{text}</Text>
            )
        },
        { title: 'Name', dataIndex: 'name', key: 'name', width: '35%' },
        {
            title: 'Usage', dataIndex: 'usage', key: 'usage', width: '10%',
            render: (usage: string) => <Tag color={usage === 'R' ? 'red' : usage === 'S' ? 'blue' : 'grey'}>{usage}</Tag>
        },
        {
            title: 'Valid Codes',
            dataIndex: 'valid_codes',
            key: 'valid_codes',
            width: '25%',
            render: (codes?: CodeDefinition[]) => {
                if (!codes || codes.length === 0) {
                    return <Text type="secondary">N/A</Text>;
                }
                return (
                    <Space size={[0, 4]} wrap>
                        {codes.map(c => (
                            <Tooltip key={c.code} title={c.description || 'No description'}>
                                <Tag>{c.code}</Tag>
                            </Tooltip>
                        ))}
                    </Space>
                );
            }
        },
    ];

    return (
        <Table
            columns={columns}
            dataSource={elements?.map(el => ({ ...el, key: el.xid }))}
            pagination={false}
            size="small"
            rowClassName={(record) => {
                return (overrides && overrides[record.xid]) ? 'ant-table-row-selected' : '';
            }}
        />
    );
};


export const EditableNodeDetails: React.FC<EditableNodeDetailsProps> = ({
    form,
    selectedNode,
    schemaContent,
    onUpdateSchema,
    isEditing,
}) => {
    const baseDefinition: SegmentDefinition | undefined = schemaContent?.segmentDefinitions[selectedNode?.segmentDefinitionId];
    const contextDefinition: ContextualDefinition | undefined = selectedNode?.contextDefinitionId ? schemaContent?.contextualDefinitions[selectedNode.contextDefinitionId] : undefined;

    const effectiveDefinition: SegmentDefinition | null = useMemo(() => {
        if (!baseDefinition) return null;
        if (!contextDefinition?.elements) return baseDefinition;

        const effective = JSON.parse(JSON.stringify(baseDefinition));
        if (contextDefinition.name) {
            effective.name = contextDefinition.name;
        }

        effective.elements = effective.elements.map((el: BaseElement) => {
            if (contextDefinition.elements![el.xid]) {
                return { ...el, ...contextDefinition.elements![el.xid] };
            }
            return el;
        });
        
        return effective;
    }, [baseDefinition, contextDefinition]);

    useEffect(() => {
        if (isEditing && selectedNode && effectiveDefinition) {
            const elementsForForm = effectiveDefinition.elements.map(el => ({
                ...el,
                valid_codes: el.valid_codes ? el.valid_codes.map(c => c.code) : [],
            }));

            form.setFieldsValue({
                structure_name: selectedNode.name,
                usage: selectedNode.usage,
                max_use: selectedNode.max_use,
                definition_name: effectiveDefinition.name,
                elements: elementsForForm,
            });
        } else {
            form.resetFields();
        }
    }, [selectedNode, effectiveDefinition, form, isEditing]);

    const handleCreateContextualOverride = () => {
        if (!selectedNode || !schemaContent || !baseDefinition) return;

        const newContextId = `${selectedNode.segmentDefinitionId}_${selectedNode.key.replace(/-/g, "_")}`;
        
        if (schemaContent.contextualDefinitions[newContextId]) {
            notification.error({ message: "Contextual override already exists with this ID." });
            return;
        }

        const newContextDef: Partial<ContextualDefinition> = {
            id: newContextId,
            name: `${baseDefinition.name} (Contextual)`,
            elements: {},
        };

        const newSchemaContent = JSON.parse(JSON.stringify(schemaContent));
        newSchemaContent.contextualDefinitions[newContextId] = newContextDef;
        newSchemaContent.structure = updateNodeByKey(newSchemaContent.structure, selectedNode.key, {
            contextDefinitionId: newContextId
        });

        onUpdateSchema(newSchemaContent);
        notification.success({ message: "Contextual override created successfully." });
    };

    if (!selectedNode || !baseDefinition) {
        return <Empty description={isEditing ? "Select a node to edit its properties." : "Select a node to see its details."} style={{ marginTop: 40 }} />;
    }

    if (!isEditing) {
        return (
            <div>
                <Title level={5} style={{ marginBottom: 24 }}>Node Details: {selectedNode.name} ({selectedNode.xid})</Title>
                <Card title="Structure Properties" size="small" style={{ marginBottom: 16 }}>
                    <Descriptions bordered column={1} size="small">
                        <Descriptions.Item label="Display Name">{selectedNode.name}</Descriptions.Item>
                        <Descriptions.Item label="Usage"><Tag>{selectedNode.usage}</Tag></Descriptions.Item>
                        {selectedNode.type === 'segment' && <Descriptions.Item label="Max Use">{selectedNode.max_use}</Descriptions.Item>}
                    </Descriptions>
                </Card>

                {contextDefinition && effectiveDefinition ? (
                    <Card title="Effective Definition (Base + Contextual Overrides)" size="small" style={{ marginBottom: 16 }}>
                        <Alert 
                            message={<Text>This node uses a specialized context: <Text strong code>{contextDefinition.id}</Text>. Highlighted rows indicate an override.</Text>} 
                            type="info" 
                            showIcon 
                            style={{marginBottom: 16}}
                        />
                         <Descriptions bordered column={1} size="small" style={{marginBottom: 16}}>
                            <Descriptions.Item label="Base Definition ID">{baseDefinition.id}</Descriptions.Item>
                            <Descriptions.Item label="Effective Name">{effectiveDefinition.name}</Descriptions.Item>
                        </Descriptions>
                        <ElementDisplayTable elements={effectiveDefinition.elements} overrides={contextDefinition.elements} />
                    </Card>
                ) : (
                    <Card title="Base Segment Definition" size="small" style={{ marginBottom: 16 }}>
                         <Descriptions bordered column={1} size="small" style={{marginBottom: 16}}>
                            <Descriptions.Item label="Definition ID">{baseDefinition.id}</Descriptions.Item>
                            <Descriptions.Item label="Name">{baseDefinition.name}</Descriptions.Item>
                        </Descriptions>
                        <ElementDisplayTable elements={baseDefinition.elements} />
                    </Card>
                )}

                {effectiveDefinition?.rules && effectiveDefinition.rules.length > 0 && (
                    <Card title="Syntax Rules" size="small">
                        {effectiveDefinition.rules.map((rule: any) => <SyntaxRuleDisplay key={rule.ruleId} rule={rule} />)}
                    </Card>
                )}
            </div>
        );
    }

    return (
        <Form form={form} layout="vertical">
            <Title level={5}>Edit Node: {selectedNode.name} ({selectedNode.xid})</Title>
            <Card title="Structure Properties" size="small" style={{ marginBottom: 16 }}>
                <Form.Item name="structure_name" label="Display Name (in tree)"><Input /></Form.Item>
                <Form.Item name="usage" label="Usage"><Select options={[{ value: "R", label: "Required" }, { value: "S", label: "Situational" }, { value: "N", label: "Not Used" }]} /></Form.Item>
                {selectedNode.type === "segment" && <Form.Item name="max_use" label="Max Use"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>}
            </Card>

            <Card title="Definition Properties" size="small">
                {!contextDefinition && (
                    <Alert
                        type="info"
                        message="This node uses the base segment definition."
                        description={<Button size="small" onClick={handleCreateContextualOverride}>Create Contextual Override to Edit</Button>}
                        showIcon
                        style={{ marginBottom: 16 }}
                    />
                )}
                
                <Form.Item name="definition_name" label="Definition Name">
                    <Input disabled={!contextDefinition} placeholder="Create an override to edit the name"/>
                </Form.Item>
                <Divider orientation="left" plain>Elements</Divider>
                <Form.List name="elements">
                    {(fields, { add, remove }) => (
                         <div style={{ display: 'flex', flexDirection: 'column', rowGap: 16 }}>
                            {fields.map(({ key, name, ...restField }) => (
                                <Card size="small" key={key} title={`Element: ${form.getFieldValue(['elements', name, 'xid'])}`} extra={<MinusCircleOutlined onClick={() => contextDefinition && remove(name)} />}>
                                    <Form.Item {...restField} name={[name, 'name']} label="Name"><Input placeholder="Element Name" disabled={!contextDefinition} /></Form.Item>
                                    <Form.Item {...restField} name={[name, 'usage']} label="Usage"><Select placeholder="Usage" style={{ width: 100 }} options={[{ value: "R" }, { value: "S" }, { value: "N" }]} disabled={!contextDefinition}/></Form.Item>
                                    <Form.Item {...restField} name={[name, 'valid_codes']} label="Valid Codes">
                                        <Select
                                            mode="tags"
                                            style={{ width: '100%' }}
                                            placeholder="Type codes and press Enter"
                                            disabled={!contextDefinition}
                                            tokenSeparators={[',']}
                                        />
                                    </Form.Item>
                                </Card>
                            ))}
                            <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />} disabled={!contextDefinition}>Add Element</Button>
                         </div>
                    )}
                </Form.List>

                 <Divider orientation="left" plain>Syntax Rules</Divider>
                 {effectiveDefinition?.rules && effectiveDefinition.rules.length > 0 ? (
                    // --- THIS IS THE FIX ---
                    // Also use the new component in edit mode for a consistent view
                    effectiveDefinition.rules.map((rule: any) => <SyntaxRuleDisplay key={rule.ruleId} rule={rule} />)
                 ) : (
                    <Text type="secondary">No syntax rules defined.</Text>
                 )}
                 <Button type="dashed" block style={{marginTop: 16}} disabled={!contextDefinition}>Add Syntax Rule</Button>

            </Card>
        </Form>
    );
};