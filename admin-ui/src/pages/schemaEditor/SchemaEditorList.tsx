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

const { Content, Sider } = Layout;
const { Title, Text } = Typography;

// ... (interfaces and helper functions remain the same) ...
interface SchemaNode {
    type: 'loop' | 'segment';
    xid: string;
    name: string;
    key?: string; 
    definitionId?: string;
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
        if(node.key) keys.push(node.key);
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
        if(node.type === 'segment' && !node.definitionId) {
            node.definitionId = node.xid;
        }
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
            const { elements, ...restValues } = newValues;
            return { ...node, ...restValues };
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
        if (node.type === 'segment' && (node.definitionId || node.xid) === xid) {
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
    const [isSharedEditingEnabled, setIsSharedEditingEnabled] = useState(false);

    const { data: schemaFilesData, isLoading: isLoadingFiles } = useCustom<string[]>({
        url: `${apiUrl}/schemas`,
        method: 'get',
    });

    const { data: schemaFileData, isLoading: isLoadingContent, refetch } = useCustom<SchemaFile>({
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
        const definitionId = selectedNode.definitionId || selectedNode.xid;
        return countXidInTree(schemaContent.structure, definitionId) > 1;
    }, [selectedNode, schemaContent]);
    
    useEffect(() => {
        if (schemaFileData?.data) {
            setSchemaContent(schemaFileData.data);
            const topLevelTreeData = transformToTreeData(JSON.parse(JSON.stringify(schemaFileData.data.structure)));
            if (topLevelTreeData.length > 0 && topLevelTreeData[0].key) {
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
        setIsSharedEditingEnabled(false);
        form.resetFields();
    }, [selectedSchema, form]);

    const onExpand = (keys: React.Key[]) => setExpandedKeys(keys);

    const handleSelect = (selectedKeys: React.Key[], info: any) => {
        if (selectedKeys.length > 0 && info.node.data) {
            if (selectedNode?.key !== info.node.data.key) {
                setIsEditing(false);
                setIsSharedEditingEnabled(false);
                setSelectedNode(info.node.data);
            }
        } else {
            setSelectedNode(null);
            setIsEditing(false);
            setIsSharedEditingEnabled(false);
        }
    };
    
    const handleSpecialize = () => {
        if (!schemaContent || !selectedNode || !selectedNode.key) return;
        
        const originalDefId = selectedNode.definitionId || selectedNode.xid;
        const newDefId = `${originalDefId}_${selectedNode.key.replace(/-/g, '_')}`;

        const newContent = JSON.parse(JSON.stringify(schemaContent!));
        newContent.segmentDefinitions[newDefId] = { ...newContent.segmentDefinitions[originalDefId] };
        
        const updateInStructure = (nodes: SchemaNode[]): SchemaNode[] => {
            return nodes.map(n => {
                if (n.key === selectedNode.key) { return { ...n, definitionId: newDefId }; }
                if (n.children) { return { ...n, children: updateInStructure(n.children) }; }
                return n;
            });
        };
        newContent.structure = updateInStructure(newContent.structure);
        
        setSchemaContent(newContent);
        
        const newNode = {...selectedNode, definitionId: newDefId };
        setSelectedNode(newNode);
        setIsSharedEditingEnabled(false);
    };

    const handleCancelEditing = () => {
        setIsEditing(false);
        setIsSharedEditingEnabled(false);
        refetch();
    };

    const handleSave = () => {
        form.validateFields().then((formValues) => {
            if (selectedSchema && schemaContent && selectedNode) {
                
                const newContent = JSON.parse(JSON.stringify(schemaContent));
                
                newContent.structure = updateNodeByKey(newContent.structure, selectedNode.key!, formValues);
                
                const definitionId = selectedNode.definitionId || selectedNode.xid;
                const segmentDef = newContent.segmentDefinitions[definitionId];
                if (segmentDef) {
                    segmentDef.name = formValues.name; 
                    if (formValues.elements) {
                        segmentDef.elements = formValues.elements;
                    }
                }

                const contentToSave = newContent;
                const cleanStructure = (nodes: SchemaNode[]) => {
                    nodes.forEach(n => {
                        delete n.key;
                        if (n.children) cleanStructure(n.children);
                    });
                };
                cleanStructure(contentToSave.structure);
    
                updateSchema({
                    resource: "schemas", id: selectedSchema, values: contentToSave,
                    successNotification: () => ({ message: "Schema saved successfully!", type: "success" }),
                    errorNotification: (error?: HttpError) => ({ message: `Save failed: ${error?.message || 'Unknown error'}`, type: "error" }),
                    meta: { 
                        onSuccess: () => {
                            setIsEditing(false);
                            setIsSharedEditingEnabled(false);
                            refetch();
                        } 
                    }
                });
            }
        });
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
                        <Tree showLine onExpand={onExpand} expandedKeys={expandedKeys} treeData={treeData} onSelect={handleSelect} />
                    )}
                    {!isTreeLoading && !selectedSchema && <Empty description="No schema selected" />}
                </Sider>
                <Content style={{ padding: '0 24px', minHeight: 280 }}>
                    <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 16, height: '32px' }}>
                        {selectedNode && !isEditing && <Button icon={<EditOutlined />} onClick={() => setIsEditing(true)}>Edit</Button>}
                        {selectedNode && isEditing && (
                            <Space>
                                <Button icon={<CloseCircleOutlined />} onClick={handleCancelEditing}>Cancel</Button>
                                <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={isSaving}>Save</Button>
                            </Space>
                        )}
                    </div>

                    {selectedNode && schemaContent ? (
                        // --- THIS IS THE FIX ---
                        // The onValuesChange prop is now completely removed.
                        <EditableNodeDetails 
                            form={form}
                            isEditing={isEditing}
                            selectedNode={selectedNode}
                            schemaContent={schemaContent}
                            onSpecialize={handleSpecialize}
                            isShared={isShared}
                            isSharedEditingEnabled={isSharedEditingEnabled}
                            onEnableSharedEditing={() => setIsSharedEditingEnabled(true)}
                        />
                    ) : (
                        <Empty description="Select a node from the tree to see details." style={{marginTop: 40}}/>
                    )}
                </Content>
            </Layout>
        </Card>
    );
};