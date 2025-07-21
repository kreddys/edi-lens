// FILE: admin-ui/src/pages/enrichment/EditableProposalForm.tsx
import React from 'react';
// --- THIS IS THE FIX ---
// Removed Table and Tag from the import
import { Form, Input, Select, Button, Space, Card, Divider } from 'antd';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import type { FormInstance } from 'antd';
// Removed unused ColumnsType import
// --- END OF FIX ---

interface EditableProposalFormProps {
    form: FormInstance;
    onFinish: (values: any) => void;
    onCancel: () => void;
    isSaving: boolean;
}

const ElementTable: React.FC = () => {
    // We will render the elements in a Form.List for full editability
    return (
        <Form.List name={["value", "elements"]}>
            {(fields, { add, remove }) => (
                <div style={{ display: 'flex', flexDirection: 'column', rowGap: 16 }}>
                    {fields.map(({ key, name, ...restField }) => (
                        <Card size="small" key={key} title={`Element ${name + 1}`} extra={<MinusCircleOutlined onClick={() => remove(name)} />}>
                            <Space align="baseline">
                                <Form.Item {...restField} name={[name, 'id']} label="ID" rules={[{ required: true }]}><Input placeholder="e.g., CLM01" /></Form.Item>
                                <Form.Item {...restField} name={[name, 'name']} label="Name" rules={[{ required: true }]}><Input placeholder="Element Name" /></Form.Item>
                                <Form.Item {...restField} name={[name, 'usage']} label="Usage" rules={[{ required: true }]}>
                                    <Select style={{ width: 120 }} options={[{value: 'R', label: 'Required'}, {value: 'S', label: 'Situational'}, {value: 'N', label: 'Not Used'}]} />
                                </Form.Item>
                                <Form.Item {...restField} name={[name, 'dataType']} label="Data Type"><Input placeholder="e.g., AN, ID, R" /></Form.Item>
                            </Space>
                            {/* Simple text inputs for now, can be expanded later */}
                            <Space align="baseline">
                                <Form.Item {...restField} name={[name, 'minLength']} label="Min Length"><Input type="number" /></Form.Item>
                                <Form.Item {...restField} name={[name, 'maxLength']} label="Max Length"><Input type="number" /></Form.Item>
                                <Form.Item {...restField} name={[name, 'description']} label="Description"><Input style={{width: 300}} /></Form.Item>
                            </Space>
                        </Card>
                    ))}
                    <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>Add Element</Button>
                </div>
            )}
        </Form.List>
    );
};


export const EditableProposalForm: React.FC<EditableProposalFormProps> = ({ form, onFinish, onCancel, isSaving }) => {
    return (
        <Form form={form} layout="vertical" onFinish={onFinish} autoComplete="off">
            <Card type="inner" title="Segment Properties">
                <Form.Item name={["value", "name"]} label="Segment Name" rules={[{ required: true }]}>
                    <Input />
                </Form.Item>
                <Form.Item name={["value", "description"]} label="Segment Description">
                    <Input.TextArea rows={2} />
                </Form.Item>
            </Card>

            <Divider orientation="left" plain>Elements</Divider>
            
            <ElementTable />

            <Form.Item style={{ marginTop: 24, textAlign: 'right' }}>
                <Space>
                    <Button onClick={onCancel}>Cancel</Button>
                    <Button type="primary" htmlType="submit" loading={isSaving}>Save Changes</Button>
                </Space>
            </Form.Item>
        </Form>
    );
};