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

interface SchemaNode {
    type: 'loop' | 'segment';
    xid: string;
    name: string;
    key?: string; // --- FIX: Mark key as optional ---
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
        if(node.key) keys.push(node.key); // Ensure key exists
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
    const [structureForm] = Form.useForm();
    const [definitionForm] = Form.useForm();
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
        // --- FIX: Use the correct form instance names ---
        structureForm.resetFields();
        definitionForm.resetFields();
    }, [selectedSchema, structureForm, definitionForm]);

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

    const handleStructureUpdate = (changedValues: any) => {
        if (!schemaContent || !selectedNode) return;
        setSchemaContent(current => {
            if (!current) return null;
            // --- FIX: Return the full SchemaFile object ---
            return {
                ...current,
                structure: updateNodeByKey(current.structure, selectedNode.key!, changedValues)
            };
        });
    };
    
    const handleDefinitionUpdate = (changedValues: any) => {
        if (!schemaContent || !selectedNode) return;
        const definitionId = selectedNode.definitionId || selectedNode.xid;
        setSchemaContent(current => ({
            ...current!,
            segmentDefinitions: {
                ...current!.segmentDefinitions,
                [definitionId]: {
                    ...current!.segmentDefinitions[definitionId],
                    ...changedValues
                }
            }
        }));
    };

    const handleSpecialize = () => {
        if (!schemaContent || !selectedNode || !selectedNode.key) return;
        
        const originalDefId = selectedNode.definitionId || selectedNode.xid;
        const newDefId = `${originalDefId}_${selectedNode.key.replace(/-/g, '_')}`;

        setSchemaContent(current => {
            const newContent = JSON.parse(JSON.stringify(current!));
            
            newContent.segmentDefinitions[newDefId] = newContent.segmentDefinitions[originalDefId];
            
            const updateInStructure = (nodes: SchemaNode[]): SchemaNode[] => {
                return nodes.map(n => {
                    if (n.key === selectedNode.key) {
                        return { ...n, definitionId: newDefId };
                    }
                    if (n.children) {
                        return { ...n, children: updateInStructure(n.children) };
                    }
                    return n;
                });
            };
            newContent.structure = updateInStructure(newContent.structure);

            setSelectedNode(prev => ({...prev!, definitionId: newDefId}));
            return newContent;
        });
    };

    const handleSave = () => {
        if (selectedSchema && schemaContent) {
            const contentToSave = JSON.parse(JSON.stringify(schemaContent));
            const cleanStructure = (nodes: SchemaNode[]) => {
                nodes.forEach(n => {
                    delete n.key;
                    if(n.children) cleanStructure(n.children);
                });
            };
            cleanStructure(contentToSave.structure);

            updateSchema({
                resource: "schemas", id: selectedSchema, values: contentToSave,
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
                    <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 16, height: '32px' }}>
                        {selectedNode && !isEditing && <Button icon={<EditOutlined />} onClick={() => setIsEditing(true)}>Edit</Button>}
                        {selectedNode && isEditing && (
                            <Space>
                                <Button icon={<CloseCircleOutlined />} onClick={() => { setIsEditing(false); structureForm.resetFields(); definitionForm.resetFields(); }}>Cancel</Button>
                                <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={isSaving}>Save</Button>
                            </Space>
                        )}
                    </div>

                    {selectedNode ? (
                        isEditing ? (
                            <EditableNodeDetails 
                                structureForm={structureForm}
                                definitionForm={definitionForm}
                                selectedNode={selectedNode}
                                schemaContent={schemaContent}
                                onStructureValuesChange={handleStructureUpdate}
                                onDefinitionValuesChange={handleDefinitionUpdate}
                                onSpecialize={handleSpecialize}
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