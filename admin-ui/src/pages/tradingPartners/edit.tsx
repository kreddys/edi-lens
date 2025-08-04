import React from "react";
import { Edit, useForm } from "@refinedev/antd";
import { Form, Input, Space, Button, Select, Card, Divider, Typography, Collapse } from "antd";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import { IResourceComponentsProps, useList, useOne } from "@refinedev/core";
import { SftpConnectionStatus } from "./SftpConnectionStatus";
import { ProfileIntegrationFields } from "./ProfileIntegrationFields"; // Import the new component

const FIELD_SOURCES = ["ISA", "GS", "FILENAME"];
const OPERATORS = ["EQUALS", "STARTS_WITH", "CONTAINS"];
const ISA_FIELD_OPTIONS = [{ value: "06", label: "06: Sender ID" }, { value: "08", label: "08: Receiver ID" }];
const GS_FIELD_OPTIONS = [{ value: "02", label: "02: Sender Code" }, { value: "03", label: "03: Receiver Code" }];

export const TradingPartnerEdit: React.FC<IResourceComponentsProps> = () => {
    const { form, formProps, saveButtonProps, id: partnerId } = useForm();
    
    const { data: sftpConfigData, isLoading: isLoadingSftp } = useOne({
        resource: 'sftp/configurations',
        id: partnerId,
        queryOptions: { enabled: !!partnerId },
    });
    const sftpConfig = sftpConfigData?.data;

    const { data: schedulesData } = useList({ resource: 'sftp/schedules' });
    const schedules = schedulesData?.data ?? [];

    return (
        <Edit saveButtonProps={saveButtonProps}>
            <Form {...formProps} layout="vertical">
                <Form.Item label="Partner Name" name="name" rules={[{ required: true }]}><Input /></Form.Item>
                <Form.Item label="Description" name="description"><Input.TextArea rows={2} /></Form.Item>
                
                <Divider>Managed SFTP Connection</Divider>
                <SftpConnectionStatus sftpConfig={sftpConfig} isLoading={isLoadingSftp} />

                <Divider>Transaction Profiles</Divider>
                <Form.List name="profiles">
                    {(fields, { add, remove }) => (
                        <div style={{ display: 'flex', flexDirection: 'column', rowGap: 16 }}>
                            {fields.map(({ key, name, ...restField }) => {
                                const profileName = form.getFieldValue(['profiles', name, 'name']) || `New Profile`;
                                
                                return (
                                <Collapse key={key} size="small" defaultActiveKey={[key]}>
                                    <Collapse.Panel header={<Typography.Text strong>{profileName}</Typography.Text>} key={key} extra={<MinusCircleOutlined onClick={() => remove(name)} />}>
                                        <Form.Item {...restField} name={[name, 'id']} hidden />
                                        <Form.Item {...restField} name={[name, 'name']} label="Profile Name" rules={[{ required: true }]}><Input onBlur={() => form.setFieldsValue({})} /></Form.Item>
                                        <Form.Item {...restField} name={[name, 'implementation_guide']} label="Implementation Guide" rules={[{ required: true }]}><Input placeholder="e.g., 005010X222A1" /></Form.Item>
                                        
                                        <Divider orientation="left" plain>Integration & Data Source</Divider>
                                        
                                        {/* Use the new component here */}
                                        <ProfileIntegrationFields 
                                            name={name} 
                                            restField={restField} 
                                            sftpConfig={sftpConfig} 
                                            schedules={schedules} 
                                        />
                                        
                                        <Divider orientation="left" plain>Matching Criteria</Divider>
                                        <Form.List name={[name, 'criteria']}>
                                            {(critFields, { add: addCrit, remove: removeCrit }) => (
                                                <div style={{ display: 'flex', flexDirection: 'column', rowGap: 16 }}>
                                                    {critFields.map(({ key: critKey, name: critName, ...restCritField }) => (
                                                        <Card size="small" key={critKey} variant="outlined">
                                                            <Space align="baseline" style={{ display: 'flex' }}>
                                                                <Form.Item {...restCritField} name={[critName, 'id']} hidden />
                                                                <Form.Item {...restCritField} name={[critName, 'field_source']} rules={[{ required: true }]}><Select placeholder="Source" style={{ width: 120 }} options={FIELD_SOURCES.map(s => ({ label: s, value: s }))} onChange={() => { const p = form.getFieldValue('profiles'); if(p?.[name]?.criteria?.[critName]) { p[name].criteria[critName].field_identifier=undefined; form.setFieldsValue({ profiles: p }); }}} /></Form.Item>
                                                                <Form.Item shouldUpdate noStyle>{() => { const fs = form.getFieldValue(['profiles', name, 'criteria', critName, 'field_source']); if(fs === 'ISA') return <Form.Item {...restCritField} name={[critName, 'field_identifier']} noStyle><Select placeholder="Identifier" style={{ width: 180 }} options={ISA_FIELD_OPTIONS} /></Form.Item>; if(fs === 'GS') return <Form.Item {...restCritField} name={[critName, 'field_identifier']} noStyle><Select placeholder="Identifier" style={{ width: 180 }} options={GS_FIELD_OPTIONS} /></Form.Item>; return <Form.Item {...restCritField} name={[critName, 'field_identifier']} noStyle><Input placeholder="Field Identifier" /></Form.Item>;}}</Form.Item>
                                                                <Form.Item {...restCritField} name={[critName, 'operator']} rules={[{ required: true }]} noStyle><Select placeholder="Operator" style={{ width: 150 }} options={OPERATORS.map(o => ({ label: o, value: o }))} /></Form.Item>
                                                                <Form.Item {...restCritField} name={[critName, 'value']} rules={[{ required: true }]} noStyle><Input placeholder="Value" /></Form.Item>
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
                            <Button type="dashed" onClick={() => add({ source_type: 'API' })} block icon={<PlusOutlined />}>
                                Add Profile
                            </Button>
                        </div>
                    )}
                </Form.List>
            </Form>
        </Edit>
    );
};