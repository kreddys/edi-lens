import React, { useEffect, useState, useMemo } from "react";
import { useApiUrl, useCustom, useUpdate, HttpError } from "@refinedev/core";
import {
    Layout,
    Select,
    Tree,
    Typography,
    Spin,
    Empty,
    Card,
    Button,
    Space,
    Form,
    Tooltip,
} from "antd";
import {
    SaveOutlined,
    PlusSquareOutlined,
    MinusSquareOutlined,
    EditOutlined,
    CloseCircleOutlined
} from "@ant-design/icons";
import type { TreeDataNode } from 'antd';
import { EditableNodeDetails } from "./EditableNodeDetails";
import { ReadOnlyNodeDetails } from "./ReadOnlyNodeDetails";

const { Content, Sider } = Layout;
const { Title, Text } = Typography;

// ... (interfaces and helper functions remain the same) ...
interface SchemaNode {
    type: 'loop' | 'segment';
    xid: string;
    name: string;
    key: string; 
    children?: SchemaNode[];
    [key: string]: any;
}

interface SchemaFile {
    transactionName: string;
    segmentDefinitions: Record<string, any>;
    structure: SchemaNode[];
}

const getAllKeys = (nodes: TreeDataNode[]): React.Key[] => {
    let keys: React.Key[] = [];
    for (const node of nodes) {
        keys.push(node.key);
        if (node.children) {
            keys = keys.concat(getAllKeys(node.children));
        }
    }
    return keys;
};

const transformToTreeData = (nodes: SchemaNode[], parentKey: string = 'root'): TreeDataNode[] => {
    return nodes.map((node, index) => {
        const key = `${parentKey}-${node.type}-${node.xid}-${index}`;
        node.key = key;
        return {
            title: (
                <Text>
                    <Text strong>{node.type === 'loop' ? 'Loop: ' : 'Segment: '}</Text>
                    {node.name} ({node.xid})
                </Text>
            ),
            key: key,
            data: node,
            children: node.children ? transformToTreeData(node.children, key) : [],
        };
    });
};

const updateNodeByKey = (nodes: SchemaNode[], key: string, newValues: any): SchemaNode[] => {
    return nodes.map(node => {
        if (node.key === key) {
            return { ...node, ...newValues };
        }
        if (node.children) {
            return { ...node, children: updateNodeByKey(node.children, key, newValues) };
        }
        return node;
    });
};

const countXidInTree = (nodes: SchemaNode[], xid: string): number => {
    let count = 0;
    for (const node of nodes) {
        if (node.type === 'segment' && node.xid === xid) {
            count++;
        }
        if (node.children) {
            count += countXidInTree(node.children, xid);
        }
    }
    return count;
};

export const SchemaEditorList: React.FC = () => {
    const [form] = Form.useForm();
    const apiUrl = useApiUrl();
    const [selectedSchema, setSelectedSchema] = useState<string | null>(null);
    const [schemaContent, setSchemaContent] = useState<SchemaFile | null>(null);
    const [selectedNode, setSelectedNode] = useState<SchemaNode | null>(null);
    const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);
    const [isEditing, setIsEditing] = useState(false);

    const { data: schemaFilesData, isLoading: isLoadingFiles } = useCustom<string[]>({
        url: `${apiUrl}/schemas`,
        method: 'get',
    });

    const { data: schemaFileData, isLoading: isLoadingContent } = useCustom<SchemaFile>({
        url: `${apiUrl}/schemas/${selectedSchema}`,
        method: "get",
        queryOptions: { enabled: !!selectedSchema },
    });

    const { mutate: updateSchema, isLoading: isSaving } = useUpdate();

    const treeData = useMemo(() => {
        if (!schemaContent) return [];
        const structureCopy = JSON.parse(JSON.stringify(schemaContent.structure));
        return transformToTreeData(structureCopy);
    }, [schemaContent]);
    
    const isShared = useMemo(() => {
        if (!selectedNode || !schemaContent || selectedNode.type !== 'segment') return false;
        return countXidInTree(schemaContent.structure, selectedNode.xid) > 1;
    }, [selectedNode, schemaContent]);
    
    useEffect(() => {
        if (schemaFileData?.data) {
            setSchemaContent(schemaFileData.data);
            // --- FIX: Only expand the top-level loop by default ---
            const topLevelTreeData = transformToTreeData(schemaFileData.data.structure);
            if (topLevelTreeData.length > 0) {
                setExpandedKeys([topLevelTreeData[0].key]);
            }
        } else {
            setSchemaContent(null);
            setExpandedKeys([]);
        }
    }, [schemaFileData]);
    
    useEffect(() => {
        setSelectedNode(null);
        setIsEditing(false);
        form.resetFields();
    }, [selectedSchema, form]);

    const onExpand = (keys: React.Key[]) => setExpandedKeys(keys);

    const handleSelect = (selectedKeys: React.Key[], info: any) => {
        if (selectedKeys.length > 0 && info.node.data) {
            if (selectedNode?.key !== info.node.key) {
                setIsEditing(false);
                setSelectedNode(info.node.data);
            }
        } else {
            setSelectedNode(null);
            setIsEditing(false);
        }
    };

    const handleNodeUpdate = (changedValues: any) => {
        if (!schemaContent || !selectedNode) return;

        setSchemaContent(currentContent => {
            if (!currentContent) return null;
            
            const newContent = JSON.parse(JSON.stringify(currentContent));
            const newStructure = updateNodeByKey(newContent.structure, selectedNode.key, changedValues);
            newContent.structure = newStructure;
            
            const segmentDef = newContent.segmentDefinitions[selectedNode.xid];
            if (segmentDef) {
                 const newDef = { ...segmentDef, ...changedValues };
                 newContent.segmentDefinitions[selectedNode.xid] = newDef;
            }
            return newContent;
        });
    };

    const handleSave = () => {
        if (selectedSchema && schemaContent) {
            updateSchema({
                resource: "schemas", id: selectedSchema, values: schemaContent,
                successNotification: () => ({ message: "Schema saved successfully!", type: "success" }),
                errorNotification: (error?: HttpError) => ({ message: `Save failed: ${error?.message || 'Unknown error'}`, type: "error" }),
                meta: { onSuccess: () => setIsEditing(false) }
            });
        }
    };

    const isTreeLoading = selectedSchema && isLoadingContent;

    return (
        <Card>
            <Select
                placeholder="Select a schema to edit"
                loading={isLoadingFiles}
                options={schemaFilesData?.data.map((f: string) => ({ label: f, value: f }))}
                onChange={(value) => setSelectedSchema(value)}
                style={{ width: 300, marginBottom: 16 }}
            />
            
            <Layout style={{ background: '#fff' }}>
                <Sider width={500} style={{ background: '#fff', padding: '0 16px', borderRight: '1px solid #f0f0f0' }}>
                     <Space style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between' }}>
                        <Title level={5} style={{ margin: 0 }}>Schema Structure</Title>
                        <Space>
                            <Tooltip title="Expand All"><Button size="small" icon={<PlusSquareOutlined />} onClick={() => setExpandedKeys(getAllKeys(treeData))} disabled={!treeData.length} /></Tooltip>
                            <Tooltip title="Collapse All"><Button size="small" icon={<MinusSquareOutlined />} onClick={() => setExpandedKeys([])} disabled={!treeData.length} /></Tooltip>
                        </Space>
                    </Space>
                    {isTreeLoading && <Spin />}
                    {!isTreeLoading && treeData.length > 0 && (
                        <Tree
                            showLine
                            onExpand={onExpand}
                            expandedKeys={expandedKeys}
                            treeData={treeData}
                            onSelect={handleSelect}
                        />
                    )}
                    {!isTreeLoading && !selectedSchema && <Empty description="No schema selected" />}
                </Sider>
                <Content style={{ padding: '0 24px', minHeight: 280 }}>
                    {/* --- FIX: New Action Bar Layout --- */}
                    <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: isEditing ? 16 : 0 }}>
                        {selectedNode && !isEditing && <Button icon={<EditOutlined />} onClick={() => setIsEditing(true)}>Edit</Button>}
                        {selectedNode && isEditing && (
                            <Space>
                                <Button icon={<CloseCircleOutlined />} onClick={() => { setIsEditing(false); form.resetFields(); }}>Cancel</Button>
                                <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={isSaving}>Save</Button>
                            </Space>
                        )}
                    </div>

                    {selectedNode ? (
                        isEditing ? (
                            <EditableNodeDetails 
                                form={form}
                                selectedNode={selectedNode}
                                schemaContent={schemaContent}
                                onValuesChange={handleNodeUpdate}
                                isShared={isShared}
                            />
                        ) : (
                            <ReadOnlyNodeDetails
                                selectedNode={selectedNode}
                                schemaContent={schemaContent}
                                isShared={isShared}
                            />
                        )
                    ) : (
                        <Empty description="Select a node from the tree to see details." style={{marginTop: 40}}/>
                    )}
                </Content>
            </Layout>
        </Card>
    );
};