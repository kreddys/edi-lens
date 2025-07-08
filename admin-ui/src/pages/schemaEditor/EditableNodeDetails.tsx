import React, { useEffect } from "react";
import { Form, Input, Select, InputNumber, Typography, Alert, Card, Button, Table, Descriptions, Tag, Divider, Space } from "antd";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import type { FormInstance } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { getLogger } from "../../utils";

const logger = getLogger("SchemaDetails");
const { Title } = Typography;

interface EditableNodeDetailsProps {
    form: FormInstance;
    selectedNode: any;
    schemaContent: any;
    onSpecialize: () => void;
    onEnableSharedEditing: () => void;
    isShared: boolean;
    isSharedEditingEnabled: boolean;
    isEditing: boolean;
}

const ReadOnlyElementTable: React.FC<{ elements: any[] }> = ({ elements }) => {
    const columns: ColumnsType<any> = [
        { title: 'Seq', dataIndex: 'seq', key: 'seq', width: '10%' },
        { title: 'Element ID', dataIndex: 'xid', key: 'xid', width: '20%' },
        { title: 'Name', dataIndex: 'name', key: 'name' },
        {
            title: 'Usage', dataIndex: 'usage', key: 'usage', width: '15%',
            render: (usage: string) => <Tag color={usage === 'R' ? 'red' : usage === 'S' ? 'blue' : 'grey'}>{usage}</Tag>
        },
        {
            title: 'Valid Codes',
            dataIndex: ['valid_codes', 'code'],
            key: 'valid_codes',
            render: (codes: (string | number)[], record: any) => {
                if (record.elements && record.elements.length > 0) {
                    return <Tag>Composite</Tag>;
                }
                return (
                    <Space size={[0, 8]} wrap>
                        {codes && codes.length > 0 ? codes.map((code) => <Tag key={code}>{code}</Tag>) : 'N/A'}
                    </Space>
                )
            }
        },
    ];

    return (
        <Table
            columns={columns}
            dataSource={elements?.map(el => ({ ...el, key: el.xid }))}
            pagination={false}
            size="small"
            expandable={{
                expandedRowRender: (record) => {
                    if (!record.elements || record.elements.length === 0) {
                        return null;
                    }
                    return (
                        <Table
                            columns={columns}
                            dataSource={record.elements.map((subEl: any) => ({ ...subEl, key: subEl.xid }))}
                            pagination={false}
                            size="small"
                        />
                    );
                },
                rowExpandable: (record) => record.elements && record.elements.length > 0,
            }}
        />
    );
};

const prepareElementsForForm = (elements: any[]): any[] => {
    if (!elements) return [];
    return elements.map(el => {
        const preparedEl = {
            ...el,
            valid_codes: { code: el.valid_codes?.code || [] },
        };
        if (el.elements && Array.isArray(el.elements)) {
            preparedEl.elements = prepareElementsForForm(el.elements);
        }
        return preparedEl;
    });
};

export const getEffectiveDefinitionId = (node: any, schema: any): string => {
    if (!node || node.type !== 'segment' || !node.key) return node?.xid;
    
    if (node.definitionId) {
        return node.definitionId;
    }
    
    const potentialSpecializedId = `${node.xid}_${node.key.replace(/-/g, '_')}`;
    if (schema?.segmentDefinitions && schema.segmentDefinitions[potentialSpecializedId]) {
        return potentialSpecializedId;
    }

    return node.xid;
};

export const EditableNodeDetails: React.FC<EditableNodeDetailsProps> = ({
    form,
    selectedNode,
    schemaContent,
    onSpecialize,
    onEnableSharedEditing,
    isShared,
    isSharedEditingEnabled,
    isEditing,
}) => {
    logger.debug("--- EditableNodeDetails RENDER ---", { isEditing, isShared });
    
    const definitionId = getEffectiveDefinitionId(selectedNode, schemaContent);
    const segmentDefinition = schemaContent.segmentDefinitions[definitionId];
    const isDefinitionEditingDisabled = isShared && !isSharedEditingEnabled;

    useEffect(() => {
        logger.groupCollapsed("--- useEffect [form population] ---");
        if (isEditing && selectedNode && segmentDefinition) {
            logger.debug("1. Received selectedNode:", JSON.parse(JSON.stringify(selectedNode)));
            logger.debug(`2. Calculated definitionId to use: '${definitionId}'`);
            
            const valuesToSet = {
                key: selectedNode.key,
                structure_name: selectedNode.name,
                definition_name: segmentDefinition.name,
                usage: selectedNode.usage,
                repeat: selectedNode.repeat,
                max_use: selectedNode.max_use,
                elements: prepareElementsForForm(segmentDefinition.elements),
            };
            logger.debug("3. Final values being set to form:", JSON.parse(JSON.stringify(valuesToSet)));
            form.setFieldsValue(valuesToSet);
        } else {
            logger.debug("Not in edit mode or no selected node/definition, resetting form.");
            form.resetFields();
        }
        logger.groupEnd();
    }, [selectedNode, segmentDefinition, form, isEditing]);

    if (!isEditing) {
        return (
             <div>
                <Title level={5} style={{ marginBottom: 24 }}>Node Details: {selectedNode.name} ({selectedNode.xid})</Title>
                <Card title="Structure Properties" size="small" style={{ marginBottom: 16 }}>
                    <Descriptions bordered column={1}>
                        <Descriptions.Item label="Display Name">{selectedNode.name}</Descriptions.Item>
                        <Descriptions.Item label="Usage">{selectedNode.usage}</Descriptions.Item>
                        {selectedNode.type === 'loop' && <Descriptions.Item label="Repeat">{selectedNode.repeat}</Descriptions.Item>}
                        {selectedNode.type === 'segment' && <Descriptions.Item label="Max Use">{selectedNode.max_use}</Descriptions.Item>}
                    </Descriptions>
                </Card>
                {selectedNode.type === "segment" && (
                    <Card title="Segment Definition Properties" size="small">
                        {segmentDefinition ? (
                            <>
                                {isShared && <Alert message="This is a shared segment definition." type="info" showIcon style={{ marginBottom: 16 }} />}
                                <Descriptions bordered column={1}>
                                    <Descriptions.Item label="Definition ID">{definitionId}</Descriptions.Item>
                                    <Descriptions.Item label="Definition Name">{segmentDefinition.name}</Descriptions.Item>
                                </Descriptions>
                                <Title level={5} style={{ marginTop: 24, marginBottom: 16 }}>Elements</Title>
                                <ReadOnlyElementTable elements={segmentDefinition.elements} />
                            </>
                        ) : (
                            <Alert message="Unlinked Segment" type="warning" showIcon />
                        )}
                    </Card>
                )}
            </div>
        );
    }

    return (
        <>
            <Form.Item name="key" hidden />
            <Title level={5}>Edit Node: {selectedNode.name} ({selectedNode.xid})</Title>
            <Card title="Structure Properties" size="small" style={{ marginBottom: 16 }}>
                <Form.Item name="structure_name" label="Display Name (in tree)"><Input /></Form.Item>
                <Form.Item name="usage" label="Usage"><Select options={[{ value: "R", label: "Required" }, { value: "S", label: "Situational" }, { value: "N", label: "Not Used" }]} /></Form.Item>
                {selectedNode.type === "loop" && <Form.Item name="repeat" label="Repeat Count"><Input placeholder="e.g., >1, 99" /></Form.Item>}
                {selectedNode.type === "segment" && <Form.Item name="max_use" label="Max Use"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>}
            </Card>

            {selectedNode.type === "segment" && segmentDefinition && (
                <Card title="Segment Definition Properties" size="small">
                    {isShared && (
                        <Alert 
                            type={isSharedEditingEnabled ? "warning" : "info"}
                            message={isSharedEditingEnabled ? "SHARED EDITING ENABLED" : "This is a shared definition"}
                            description={
                                <Space>
                                    <Button size="small" onClick={onSpecialize}>Create Specialized Version</Button>
                                    {!isSharedEditingEnabled && <><Divider type="vertical" /> <Button size="small" onClick={onEnableSharedEditing}>Edit All Shared Instances</Button></>}
                                </Space>
                            }
                            showIcon
                            style={{ marginBottom: 16 }}
                        />
                    )}
                    <Form.Item name="definition_name" label="Definition Name"><Input disabled={isDefinitionEditingDisabled} /></Form.Item>
                    <Divider orientation="left" plain>Elements</Divider>
                    <Form.List name="elements">
                        {(fields, { add, remove }) => (
                            <div style={{ display: 'flex', flexDirection: 'column', rowGap: 16 }}>
                                {fields.map(({ key, name, ...restField }) => (
                                    <Card size="small" key={key} title={`Element: ${form.getFieldValue(['elements', name, 'xid'])}`} extra={<MinusCircleOutlined onClick={() => !isDefinitionEditingDisabled && remove(name)} />}>
                                        <Form.Item {...restField} name={[name, 'name']} label="Name"><Input placeholder="Element Name" disabled={isDefinitionEditingDisabled} /></Form.Item>
                                        <Form.Item {...restField} name={[name, 'usage']} label="Usage"><Select placeholder="Usage" style={{ width: 100 }} options={[{ value: "R" }, { value: "S" }, { value: "N" }]} disabled={isDefinitionEditingDisabled}/></Form.Item>
                                        
                                        <Form.Item shouldUpdate noStyle>
                                            {() => {
                                                const subElements = form.getFieldValue(['elements', name, 'elements']);
                                                if (Array.isArray(subElements)) {
                                                    return (
                                                        <>
                                                            <Divider orientation="left" plain>Sub-Elements</Divider>
                                                            <div style={{ marginLeft: 24, display: 'flex', flexDirection: 'column', rowGap: 16 }}>
                                                                <Form.List name={[name, 'elements']}>
                                                                    {(subFields, { add: addSub, remove: removeSub }) => (
                                                                        <>
                                                                            {subFields.map(({ key: subKey, name: subName, ...restSubField }) => (
                                                                                <Card size="small" key={subKey} title={`Sub: ${form.getFieldValue(['elements', name, 'elements', subName, 'xid'])}`} extra={<MinusCircleOutlined onClick={() => !isDefinitionEditingDisabled && removeSub(subName)} />}>
                                                                                    <Form.Item {...restSubField} name={[subName, 'name']} label="Name"><Input placeholder="Sub-Element Name" disabled={isDefinitionEditingDisabled} /></Form.Item>
                                                                                    <Form.Item {...restSubField} name={[subName, 'usage']} label="Usage"><Select placeholder="Usage" style={{ width: 100 }} options={[{ value: "R" }, { value: "S" }, { value: "N" }]} disabled={isDefinitionEditingDisabled}/></Form.Item>
                                                                                    <Form.Item {...restSubField} name={[subName, 'valid_codes', 'code']} label="Valid Codes">
                                                                                        <Select mode="tags" style={{ width: '100%' }} tokenSeparators={[',']} placeholder="Type codes and press Enter" disabled={isDefinitionEditingDisabled} />
                                                                                    </Form.Item>
                                                                                </Card>
                                                                            ))}
                                                                            <Button type="dashed" onClick={() => addSub()} block icon={<PlusOutlined />} disabled={isDefinitionEditingDisabled}>Add Sub-Element</Button>
                                                                        </>
                                                                    )}
                                                                </Form.List>
                                                            </div>
                                                        </>
                                                    );
                                                }
                                                return (
                                                    <Form.Item {...restField} name={[name, 'valid_codes', 'code']} label="Valid Codes">
                                                         <Select mode="tags" style={{ width: '100%' }} tokenSeparators={[',']} placeholder="Type codes and press Enter" disabled={isDefinitionEditingDisabled} />
                                                    </Form.Item>
                                                );
                                            }}
                                        </Form.Item>
                                    </Card>
                                ))}
                                <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />} disabled={isDefinitionEditingDisabled}>Add Element</Button>
                            </div>
                        )}
                    </Form.List>
                </Card>
            )}
        </>
    );
};