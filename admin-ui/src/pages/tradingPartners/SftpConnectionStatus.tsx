import React from 'react';
import { Card, Descriptions, Tag, Spin, Empty, Typography } from 'antd';

interface SftpConnectionStatusProps {
    sftpConfig: any;
    isLoading: boolean;
}

export const SftpConnectionStatus: React.FC<SftpConnectionStatusProps> = ({ sftpConfig, isLoading }) => {
    if (isLoading) {
        return (
            <Card>
                <Spin />
            </Card>
        );
    }

    if (!sftpConfig) {
        return (
            <Card>
                <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description={
                        <Typography.Text type="secondary">
                            No Managed SFTP connection is configured for this partner. <br />
                            An administrator must enable this via the backend.
                        </Typography.Text>
                    }
                />
            </Card>
        );
    }
    
    return (
        <Card size="small">
            <Descriptions bordered size="small" column={2}>
                <Descriptions.Item label="Status">
                    <Tag color={sftpConfig.sftp_enabled ? 'green' : 'red'}>
                        {sftpConfig.sftp_enabled ? 'Enabled' : 'Disabled'}
                    </Tag>
                </Descriptions.Item>
                {/* --- THIS IS THE FIX: Display the logical username --- */}
                <Descriptions.Item label="SFTP User">
                    <Typography.Text copyable>
                        {sftpConfig.tenant_partner_username}
                    </Typography.Text>
                </Descriptions.Item>
                <Descriptions.Item label="Authentication">
                    {sftpConfig.authentication_type}
                </Descriptions.Item>
                {/* --- REMOVED: The confusing "Home Directory" item --- */}
            </Descriptions>
        </Card>
    );
};