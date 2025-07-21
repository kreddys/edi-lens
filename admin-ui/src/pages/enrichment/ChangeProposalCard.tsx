// FILE: admin-ui/src/pages/enrichment/ChangeProposalCard.tsx
import React, { useState, useEffect } from 'react';
// --- FIX: Add Input to the import ---
import { Card, Tag, Typography, Button, Space, Collapse, Segmented, Form, Input } from 'antd';
import { CheckOutlined, CloseOutlined, EditOutlined } from '@ant-design/icons';
import ReactDiffViewer from 'react-diff-viewer-continued';
import { EditableProposalForm } from './EditableProposalForm';

const { Text } = Typography;

type TPatch = {
    op: 'add' | 'replace' | 'remove';
    path: string;
    value?: any;
};

type TProposal = {
    patch: TPatch;
    status: 'pending' | 'accepted' | 'rejected';
};

interface ChangeProposalCardProps {
    proposal: TProposal;
    onDecision: (status: 'accepted' | 'rejected') => void;
    onUpdatePatch: (newPatch: TPatch) => void;
}

// --- FIX: Move helper functions outside the component body ---
const getTagColor = (op: string) => {
    if (op === 'add') return 'success';
    if (op === 'replace') return 'warning';
    if (op === 'remove') return 'error';
    return 'default';
};

const getStatusColor = (status: string) => {
    if (status === 'accepted') return 'green';
    if (status === 'rejected') return 'red';
    return 'blue';
};

const getPanelHeader = (proposal: TProposal) => {
    const { patch, status } = proposal;
    let summary = `New definition for ${patch.path.split('/').pop()}`;
    if (patch.op === 'replace') {
        summary = `Update to ${patch.path}`;
    } else if (patch.op === 'remove') {
        summary = `Removal of ${patch.path}`;
    }

    return (
        <Space>
            <Tag color={getStatusColor(status)}>{status.toUpperCase()}</Tag>
            <Text>{summary}</Text>
        </Space>
    );
};
// --- END OF FIX ---


export const ChangeProposalCard: React.FC<ChangeProposalCardProps> = ({ proposal, onDecision, onUpdatePatch }) => {
    const [form] = Form.useForm();
    const { patch, status } = proposal;

    const [viewMode, setViewMode] = useState<'business' | 'developer'>('business');
    const [isEditing, setIsEditing] = useState<boolean>(false);

    useEffect(() => {
        form.setFieldsValue(patch);
    }, [patch, form]);

    const handleAcceptAndEdit = () => {
        setIsEditing(true);
        if (status !== 'accepted') {
            onDecision('accepted');
        }
    };

    const handleSaveChanges = (values: any) => {
        console.log("Saving changes:", values);
        onUpdatePatch(values);
        setIsEditing(false);
    };

    const handleCancelEdit = () => {
        form.setFieldsValue(patch);
        setIsEditing(false);
    };

    const actions = (
        <Space>
            <Button icon={<CheckOutlined />} onClick={() => onDecision('accepted')} disabled={status === 'accepted' || isEditing}>
                Accept
            </Button>
            <Button icon={<EditOutlined />} onClick={handleAcceptAndEdit} disabled={isEditing}>
                Accept & Edit
            </Button>
            <Button danger icon={<CloseOutlined />} onClick={() => onDecision('rejected')} disabled={status === 'rejected' || isEditing}>
                Reject
            </Button>
        </Space>
    );

    const renderContent = () => {
        if (isEditing) {
            return (
                <EditableProposalForm
                    form={form}
                    onFinish={handleSaveChanges}
                    onCancel={handleCancelEdit}
                    isSaving={false}
                />
            );
        }

        return (
            <>
                <Segmented
                    options={[{ label: 'Business View', value: 'business' }, { label: 'Developer View (Diff)', value: 'developer' }]}
                    value={viewMode}
                    onChange={(value) => setViewMode(value as any)}
                    style={{ marginBottom: 16 }}
                />

                {viewMode === 'developer' ? (
                    <ReactDiffViewer
                        oldValue={patch.op === 'add' ? '' : '... (old value not yet implemented) ...'}
                        newValue={JSON.stringify(patch.value, null, 2)}
                        splitView={false}
                        hideLineNumbers={true}
                    />
                ) : (
                    <Form layout="vertical" disabled>
                        <Form.Item label="Segment Name">
                            <Input value={patch.value?.name} />
                        </Form.Item>
                        <Form.Item label="Segment Description">
                            <Input.TextArea value={patch.value?.description} rows={2} />
                        </Form.Item>
                        <Form.Item label="Usage">
                            <Input value={patch.value?.usage} />
                        </Form.Item>
                        <Text strong>Elements:</Text>
                        <pre style={{ maxHeight: 200, overflow: 'auto', background: '#f5f5f5', padding: 8 }}>
                            {JSON.stringify(patch.value?.elements, null, 2)}
                        </pre>
                    </Form>
                )}
            </>
        );
    }

    return (
        <Collapse defaultActiveKey={['1']}>
            {/* --- FIX: Call the helper function --- */}
            <Collapse.Panel header={getPanelHeader(proposal)} key="1">
                <Card
                    type="inner"
                    title={
                        <Space>
                            {/* --- FIX: Call the helper function --- */}
                            <Tag color={getTagColor(patch.op)}>{patch.op.toUpperCase()}</Tag>
                            <Text>Target:</Text>
                            <Typography.Text code>{patch.path}</Typography.Text>
                        </Space>
                    }
                    extra={!isEditing && actions}
                    style={{ opacity: status === 'rejected' ? 0.5 : 1 }}
                >
                    {renderContent()}
                </Card>
            </Collapse.Panel>
        </Collapse>
    );
};