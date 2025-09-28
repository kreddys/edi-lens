import React from "react";
import {
    List,
    useTable,
    EditButton,
    ShowButton,
    DeleteButton,
} from "@refinedev/antd";
import { Button, Space, Table, Tag, Input } from "antd";
import { PlusOutlined, SearchOutlined } from "@ant-design/icons";

export const FlowList: React.FC = () => {
    const { tableProps } = useTable({
        syncWithLocation: true,
        pagination: {
            pageSize: 10,
        },
    });

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'running': return 'green';
            case 'stopped': return 'default';
            case 'invalid': return 'red';
            case 'deployed': return 'blue';
            case 'unknown': return 'orange';
            default: return 'default';
        }
    };

    return (
        <List
            headerProps={{
                extra: (
                    <Button type="primary" icon={<PlusOutlined />} href="/flows/create">
                        Create New Flow
                    </Button>
                ),
            }}
        >
            <Table {...tableProps} rowKey="id">
                <Table.Column 
                    dataIndex="name" 
                    title="Name"
                    filterDropdown={({ setSelectedKeys, selectedKeys, confirm, clearFilters }) => (
                        <div style={{ padding: 8 }}>
                            <Input
                                placeholder="Search flow name"
                                value={selectedKeys[0]}
                                onChange={(e) => setSelectedKeys(e.target.value ? [e.target.value] : [])}
                                onPressEnter={() => confirm()}
                                style={{ marginBottom: 8, display: 'block' }}
                            />
                            <Space>
                                <Button
                                    type="primary"
                                    onClick={() => confirm()}
                                    icon={<SearchOutlined />}
                                    size="small"
                                    style={{ width: 90 }}
                                >
                                    Search
                                </Button>
                                <Button onClick={() => clearFilters?.()} size="small" style={{ width: 90 }}>
                                    Reset
                                </Button>
                            </Space>
                        </div>
                    )}
                    filterIcon={(filtered) => <SearchOutlined style={{ color: filtered ? '#1890ff' : undefined }} />}
                />
                <Table.Column 
                    dataIndex="status" 
                    title="Status" 
                    render={(status) => (
                        <Tag color={getStatusColor(status)}>
                            {status === 'unknown' ? 'Not Started' : status}
                        </Tag>
                    )}
                    filters={[
                        { text: 'Running', value: 'running' },
                        { text: 'Stopped', value: 'stopped' },
                        { text: 'Invalid', value: 'invalid' },
                        { text: 'Not Started', value: 'unknown' },
                    ]}
                />
                <Table.Column dataIndex="description" title="Description" />
                <Table.Column 
                    dataIndex="created_at" 
                    title="Created" 
                    render={(created_at) => (
                        <div style={{ fontSize: '12px' }}>
                            {created_at === "Not available" ? (
                                <span style={{ color: '#999', fontStyle: 'italic' }}>
                                    Not available
                                </span>
                            ) : (
                                new Date(created_at).toLocaleDateString()
                            )}
                        </div>
                    )}
                />
                <Table.Column
                    title="Actions"
                    dataIndex="actions"
                    render={(_, record: any) => (
                        <Space>
                            <ShowButton hideText size="small" recordItemId={record.id} />
                            <EditButton hideText size="small" recordItemId={record.id} />
                            <DeleteButton hideText size="small" recordItemId={record.id} />
                        </Space>
                    )}
                />
            </Table>
        </List>
    );
};