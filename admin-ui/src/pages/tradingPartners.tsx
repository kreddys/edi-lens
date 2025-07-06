import React from "react";
import {
  useTable,
  List,
  Create,
  EditButton,
  useForm,
} from "@refinedev/antd";
import { Table, Form, Input, Space, Button, Select, Card, Divider, Typography, Collapse } from "antd";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import { IResourceComponentsProps, BaseRecord } from "@refinedev/core";

// --- Data for Guided Dropdowns ---
const FIELD_SOURCES = ["ISA", "GS", "FILENAME"];
const OPERATORS = ["EQUALS", "STARTS_WITH", "CONTAINS"];

const ISA_FIELD_OPTIONS = [
    { value: "06", label: "06: Sender ID" },
    { value: "08", label: "08: Receiver ID" },
];

const GS_FIELD_OPTIONS = [
    { value: "02", label: "02: Sender Code" },
    { value: "03", label: "03: Receiver Code" },
];

// --- Components ---

export const TradingPartnerList: React.FC<IResourceComponentsProps> = () => {
  const { tableProps } = useTable();
  return (
    <List>
      <Table {...tableProps} rowKey="id">
        <Table.Column dataIndex="id" title="ID" />
        <Table.Column dataIndex="name" title="Name" />
        <Table.Column dataIndex="description" title="Description" />
        <Table.Column dataIndex="tenant_id" title="Tenant" />
        <Table.Column
          title="Actions"
          dataIndex="actions"
          render={(_, record: BaseRecord) => (
            <Space>
              <EditButton hideText size="small" recordItemId={record.id} />
            </Space>
          )}
        />
      </Table>
    </List>
  );
};

export const TradingPartnerCreate: React.FC<IResourceComponentsProps> = () => {
    const { form, formProps, saveButtonProps } = useForm();

    return (
        <Create saveButtonProps={saveButtonProps}>
            <Form {...formProps} layout="vertical">
                <Form.Item label="Partner Name" name="name" rules={[{ required: true }]}>
                    <Input />
                </Form.Item>
                <Form.Item label="Description" name="description">
                    <Input.TextArea rows={2} />
                </Form.Item>

                <Divider>Profiles</Divider>

                <Form.List name="profiles">
                    {(fields, { add, remove }) => (
                        <div style={{ display: 'flex', flexDirection: 'column', rowGap: 16 }}>
                            {fields.map(({ key, name, ...restField }, index) => {
                                const profileName = form.getFieldValue(['profiles', name, 'name']) || `Profile ${index + 1}`;
                                return (
                                <Collapse key={key} size="small" defaultActiveKey={[key]}>
                                    <Collapse.Panel
                                        header={<Typography.Text strong>{profileName}</Typography.Text>}
                                        key={key}
                                        extra={<MinusCircleOutlined onClick={() => remove(name)} />}
                                    >
                                        <Form.Item {...restField} name={[name, 'name']} label="Profile Name" rules={[{ required: true }]}>
                                            <Input onBlur={() => form.setFieldsValue({})} />
                                        </Form.Item>
                                        <Form.Item {...restField} name={[name, 'implementation_guide']} label="Implementation Guide" rules={[{ required: true }]}>
                                            <Input placeholder="e.g., 005010X222A1" />
                                        </Form.Item>
                                        <Divider orientation="left" plain>Criteria</Divider>
                                        {/* --- Nested and Guided Criteria Form --- */}
                                        <Form.List name={[name, 'criteria']}>
                                            {(critFields, { add: addCrit, remove: removeCrit }) => (
                                                <div style={{ display: 'flex', flexDirection: 'column', rowGap: 16 }}>
                                                    {critFields.map(({ key: critKey, name: critName, ...restCritField }) => (
                                                        <Card size="small" key={critKey}>
                                                            <Space align="baseline" style={{ display: 'flex' }}>
                                                                <Form.Item {...restCritField} name={[critName, 'field_source']} rules={[{ required: true }]}>
                                                                    <Select
                                                                        placeholder="Source"
                                                                        style={{ width: 120 }}
                                                                        options={FIELD_SOURCES.map(s => ({ label: s, value: s }))}
                                                                        onChange={() => {
                                                                            // When the source changes, reset the identifier value
                                                                            const profiles = form.getFieldValue('profiles');
                                                                            if (profiles && profiles[name] && profiles[name].criteria) {
                                                                                profiles[name].criteria[critName].field_identifier = undefined;
                                                                                form.setFieldsValue({ profiles });
                                                                            }
                                                                        }}
                                                                    />
                                                                </Form.Item>
                                                                {/* --- This is the conditional input --- */}
                                                                <Form.Item shouldUpdate noStyle>
                                                                    {() => {
                                                                        const fieldSource = form.getFieldValue(['profiles', name, 'criteria', critName, 'field_source']);
                                                                        if (fieldSource === 'ISA') {
                                                                            return <Form.Item {...restCritField} name={[critName, 'field_identifier']} noStyle><Select placeholder="Identifier" style={{ width: 180 }} options={ISA_FIELD_OPTIONS} /></Form.Item>;
                                                                        }
                                                                        if (fieldSource === 'GS') {
                                                                            return <Form.Item {...restCritField} name={[critName, 'field_identifier']} noStyle><Select placeholder="Identifier" style={{ width: 180 }} options={GS_FIELD_OPTIONS} /></Form.Item>;
                                                                        }
                                                                        return <Form.Item {...restCritField} name={[critName, 'field_identifier']} noStyle><Input placeholder="Field Identifier" /></Form.Item>;
                                                                    }}
                                                                </Form.Item>
                                                                <Form.Item {...restCritField} name={[critName, 'operator']} rules={[{ required: true }]} noStyle>
                                                                    <Select placeholder="Operator" style={{ width: 150 }} options={OPERATORS.map(o => ({ label: o, value: o }))} />
                                                                </Form.Item>
                                                                <Form.Item {...restCritField} name={[critName, 'value']} rules={[{ required: true }]} noStyle>
                                                                    <Input placeholder="Value" />
                                                                </Form.Item>
                                                                <MinusCircleOutlined onClick={() => removeCrit(critName)} />
                                                            </Space>
                                                        </Card>
                                                    ))}
                                                    <Button type="dashed" onClick={() => addCrit()} block icon={<PlusOutlined />}>Add Criterion</Button>
                                                </div>
                                            )}
                                        </Form.List>
                                    </Collapse.Panel>
                                </Collapse>
                            )})}
                            <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>Add Profile</Button>
                        </div>
                    )}
                </Form.List>
            </Form>
        </Create>
    );
};