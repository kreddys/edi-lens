import React, { useState, useEffect } from 'react';
import {
    Modal,
    Form,
    Input,
    Button,
    Space,
    Typography,
    Switch,
    Table,
    notification,
    Popconfirm,
    Card,
    Tag
} from 'antd';
import { EditOutlined, DeleteOutlined, PlusOutlined, SaveOutlined } from '@ant-design/icons';
import { flowAPI } from '../providers/data';

const { Text } = Typography;
const { TextArea } = Input;

interface Parameter {
    name: string;
    value: string;
    description: string;
    sensitive: boolean;
}

interface ParameterEditModalProps {
    open: boolean;
    onClose: () => void;
    flowId: string;
    flowName: string;
    initialParameters?: Record<string, any>;
    onSuccess?: () => void;
}

export const ParameterEditModal: React.FC<ParameterEditModalProps> = ({
    open,
    onClose,
    flowId,
    flowName,
    initialParameters = {},
    onSuccess
}) => {
    const [form] = Form.useForm();
    const [parameters, setParameters] = useState<Parameter[]>([]);
    const [loading, setLoading] = useState(false);
    const [editingKey, setEditingKey] = useState<string>('');

    useEffect(() => {
        if (open && initialParameters) {
            // Convert initial parameters to editable format
            const paramArray = Object.entries(initialParameters).map(([name, value]) => {
                let paramValue = '';
                let paramDescription = '';
                let isSensitive = false;

                if (typeof value === 'object' && value !== null) {
                    const paramObj = value as any;
                    paramValue = paramObj.value || '';
                    paramDescription = paramObj.description || '';
                    isSensitive = paramObj.sensitive || false;

                    // Handle stringified template parameter objects
                    if (typeof paramValue === 'string' && paramValue.startsWith('{') && paramValue.includes("'description'")) {
                        try {
                            const jsonString = paramValue.replace(/'/g, '"');
                            const parsedParam = JSON.parse(jsonString);
                            paramValue = parsedParam.default || parsedParam.value || '';
                            paramDescription = parsedParam.description || paramDescription;
                        } catch (e) {
                            console.warn('Failed to parse parameter value:', paramValue);
                        }
                    }
                } else {
                    paramValue = String(value);
                }

                return {
                    name,
                    value: paramValue,
                    description: paramDescription,
                    sensitive: isSensitive
                };
            });

            setParameters(paramArray);
        }
    }, [open, initialParameters]);

    const handleSave = async () => {
        try {
            setLoading(true);
            
            // Convert parameters back to API format
            const parameterUpdates = parameters.map(param => ({
                name: param.name,
                value: param.value,
                description: param.description || `Parameter ${param.name}`,
                sensitive: param.sensitive
            }));

            await flowAPI.updateFlowParameters(flowId, parameterUpdates);
            
            notification.success({
                message: 'Parameters Updated',
                description: `Successfully updated ${parameterUpdates.length} parameter(s) for flow "${flowName}"`,
            });

            onSuccess?.();
            onClose();
        } catch (error: any) {
            console.error('Error updating parameters:', error);
            notification.error({
                message: 'Update Failed',
                description: error?.response?.data?.message || 'Failed to update flow parameters',
            });
        } finally {
            setLoading(false);
        }
    };

    const addParameter = () => {
        const newParam: Parameter = {
            name: `new_parameter_${parameters.length + 1}`,
            value: '',
            description: '',
            sensitive: false
        };
        setParameters([...parameters, newParam]);
        setEditingKey(newParam.name);
    };

    const deleteParameter = (paramName: string) => {
        setParameters(parameters.filter(p => p.name !== paramName));
        if (editingKey === paramName) {
            setEditingKey('');
        }
    };

    const updateParameter = (paramName: string, field: keyof Parameter, value: any) => {
        setParameters(parameters.map(p => 
            p.name === paramName ? { ...p, [field]: value } : p
        ));
    };

    const isEditing = (paramName: string) => paramName === editingKey;

    const EditableCell: React.FC<{
        editing: boolean;
        dataIndex: keyof Parameter;
        title: string;
        record: Parameter;
        children: React.ReactNode;
    }> = ({ editing, dataIndex, title, record, children, ...restProps }) => {
        if (!editing) {
            return <td {...restProps}>{children}</td>;
        }

        let inputNode: React.ReactNode;

        if (dataIndex === 'sensitive') {
            inputNode = (
                <Switch
                    checked={record.sensitive}
                    onChange={(checked) => updateParameter(record.name, 'sensitive', checked)}
                    size="small"
                />
            );
        } else if (dataIndex === 'description') {
            inputNode = (
                <TextArea
                    value={record.description}
                    onChange={(e) => updateParameter(record.name, 'description', e.target.value)}
                    placeholder="Parameter description"
                    autoSize={{ minRows: 1, maxRows: 3 }}
                />
            );
        } else if (dataIndex === 'value') {
            inputNode = (
                <Input
                    value={record.value}
                    onChange={(e) => updateParameter(record.name, 'value', e.target.value)}
                    placeholder="Parameter value"
                    type={record.sensitive ? 'password' : 'text'}
                />
            );
        } else if (dataIndex === 'name') {
            inputNode = (
                <Input
                    value={record.name}
                    onChange={(e) => updateParameter(record.name, 'name', e.target.value)}
                    placeholder="Parameter name"
                />
            );
        } else {
            inputNode = children;
        }

        return <td {...restProps}>{inputNode}</td>;
    };

    const columns = [
        {
            title: 'Parameter Name',
            dataIndex: 'name',
            key: 'name',
            width: '25%',
            onCell: (record: Parameter) => ({
                record,
                dataIndex: 'name',
                title: 'Parameter Name',
                editing: isEditing(record.name),
            }),
            render: (text: string, record: Parameter) => {
                if (isEditing(record.name)) return text;
                return (
                    <div>
                        <Text code strong>{text}</Text>
                        {record.sensitive && (
                            <Tag color="orange" style={{ marginLeft: 8, fontSize: '11px' }}>
                                SENSITIVE
                            </Tag>
                        )}
                    </div>
                );
            },
        },
        {
            title: 'Description',
            dataIndex: 'description',
            key: 'description',
            width: '30%',
            onCell: (record: Parameter) => ({
                record,
                dataIndex: 'description',
                title: 'Description',
                editing: isEditing(record.name),
            }),
            render: (text: string) => {
                if (editingKey) return text;
                return (
                    <Text type={text ? 'secondary' : 'secondary'} italic={!text}>
                        {text || 'No description'}
                    </Text>
                );
            },
        },
        {
            title: 'Value',
            dataIndex: 'value',
            key: 'value',
            width: '25%',
            onCell: (record: Parameter) => ({
                record,
                dataIndex: 'value',
                title: 'Value',
                editing: isEditing(record.name),
            }),
            render: (text: string, record: Parameter) => {
                if (isEditing(record.name)) return text;
                if (record.sensitive) {
                    return <Text code>{'*'.repeat(Math.min(text.length, 8))}</Text>;
                }
                return <Text code>{text || <Text type="secondary" italic>Empty</Text>}</Text>;
            },
        },
        {
            title: 'Sensitive',
            dataIndex: 'sensitive',
            key: 'sensitive',
            width: '10%',
            onCell: (record: Parameter) => ({
                record,
                dataIndex: 'sensitive',
                title: 'Sensitive',
                editing: isEditing(record.name),
            }),
            render: (sensitive: boolean, record: Parameter) => {
                if (isEditing(record.name)) return null;
                return <Switch checked={sensitive} size="small" disabled />;
            },
        },
        {
            title: 'Actions',
            key: 'actions',
            width: '10%',
            render: (_: any, record: Parameter) => {
                const editable = isEditing(record.name);
                return editable ? (
                    <Space>
                        <Button
                            type="text"
                            size="small"
                            onClick={() => setEditingKey('')}
                            icon={<SaveOutlined />}
                        />
                    </Space>
                ) : (
                    <Space>
                        <Button
                            type="text"
                            size="small"
                            disabled={editingKey !== ''}
                            onClick={() => setEditingKey(record.name)}
                            icon={<EditOutlined />}
                        />
                        <Popconfirm
                            title="Delete parameter?"
                            onConfirm={() => deleteParameter(record.name)}
                            okText="Delete"
                            cancelText="Cancel"
                            disabled={editingKey !== ''}
                        >
                            <Button
                                type="text"
                                size="small"
                                danger
                                disabled={editingKey !== ''}
                                icon={<DeleteOutlined />}
                            />
                        </Popconfirm>
                    </Space>
                );
            },
        },
    ];

    return (
        <Modal
            title={`Edit Parameters - ${flowName}`}
            open={open}
            onCancel={onClose}
            width={1000}
            footer={[
                <Button key="cancel" onClick={onClose} disabled={loading}>
                    Cancel
                </Button>,
                <Button
                    key="add"
                    type="dashed"
                    onClick={addParameter}
                    disabled={loading || editingKey !== ''}
                    icon={<PlusOutlined />}
                >
                    Add Parameter
                </Button>,
                <Button
                    key="save"
                    type="primary"
                    loading={loading}
                    onClick={handleSave}
                    disabled={editingKey !== ''}
                    icon={<SaveOutlined />}
                >
                    Save Changes
                </Button>,
            ]}
        >
            <div style={{ marginBottom: 16 }}>
                <Text type="secondary">
                    Configure parameters for your flow. Sensitive parameters will be masked and encrypted.
                </Text>
            </div>

            <Form form={form} component={false}>
                <Table
                    components={{
                        body: {
                            cell: EditableCell,
                        },
                    }}
                    dataSource={parameters}
                    columns={columns}
                    rowKey="name"
                    pagination={false}
                    size="small"
                    locale={{
                        emptyText: 'No parameters defined. Click "Add Parameter" to create one.'
                    }}
                />
            </Form>

            {editingKey && (
                <Card size="small" style={{ marginTop: 16, backgroundColor: '#f0f7ff' }}>
                    <Text type="secondary">
                        <strong>Editing:</strong> Click the save icon or press Enter to confirm changes.
                        Click outside to cancel.
                    </Text>
                </Card>
            )}
        </Modal>
    );
};