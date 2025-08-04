import React from 'react';
import { Form, Select, Input, Card, Alert } from 'antd';
import { BaseRecord } from '@refinedev/core';

interface ProfileIntegrationFieldsProps {
    name: number;
    restField: Record<string, any>;
    sftpConfig?: BaseRecord;
    schedules: BaseRecord[];
}

export const ProfileIntegrationFields: React.FC<ProfileIntegrationFieldsProps> = ({ name, restField, sftpConfig, schedules }) => {
    const sourceType = Form.useWatch(['profiles', name, 'source_type']);

    return (
        <>
            <Form.Item
                {...restField}
                name={[name, 'source_type']}
                label="Data Source for this Profile"
                initialValue="API"
            >
                <Select
                    options={[
                        { label: 'API (Real-time, Pushed to EDI Lens)', value: 'API' },
                        { label: 'Managed SFTP (Batch, Pulled by EDI Lens)', value: 'EDI_LENS_SFTP' },
                    ]}
                />
            </Form.Item>

            {sourceType === 'EDI_LENS_SFTP' && (
                // --- THIS IS THE FIX: Changed 'variant' to 'type' for the correct styling ---
                <Card size="small" style={{ marginBottom: 16 }} type="inner">
                    {!sftpConfig?.sftp_enabled && (
                            <Alert 
                            message="The partner's main SFTP connection is not enabled." 
                            description="These settings will be ignored until the connection is enabled by an administrator."
                            type="warning" showIcon style={{ marginBottom: 16 }} 
                            />
                    )}
                    <Form.Item
                        {...restField}
                        name={[name, 'file_name_patterns']}
                        label="File Name Patterns (JSON Array)"
                        tooltip='Example: ["claims_*.edi", "INV_*_*.x12"]'
                        rules={[{ required: true, message: 'File patterns are required for SFTP integration.' }]}
                    >
                        <Input placeholder='["*.edi"]' disabled={!sftpConfig?.sftp_enabled} />
                    </Form.Item>
                    <Form.Item
                        {...restField}
                        name={[name, 'poll_schedule_id']}
                        label="Polling Schedule"
                    >
                        <Select
                            options={schedules.map(s => ({ label: `${s.name} (${s.description})`, value: s.id }))}
                            placeholder="Select a processing schedule"
                            disabled={!sftpConfig?.sftp_enabled}
                            allowClear
                        />
                    </Form.Item>
                </Card>
            )}
        </>
    );
};