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
    CloseCircleOutlined,
} from "@ant-design/icons";
import type { TreeDataNode } from "antd";
import { EditableNodeDetails } from "./EditableNodeDetails";
import { getLogger } from "../../utils";

const logger = getLogger("SchemaEditor");
const { Content, Sider } = Layout;
const { Title, Text } = Typography;

interface SchemaNode {
    type: "loop" | "segment";
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
        if (node.key) keys.push(node.key);
        if (node.children) {
            keys = keys.concat(getAllKeys(node.children));
        }
    }
    return keys;
};

const transformToTreeData = (nodes: SchemaNode[], parentKey: string = "root"): TreeDataNode[] => {
    return nodes.map((node, index) => {
        const key = `${parentKey}-${node.type}-${node.xid}-${index}`;
        const dataNode = { ...node, key };
        return {
            title: (
                <Text>
                    <Text strong>{node.type === "loop" ? "Loop: " : "Segment: "}</Text>
                    {node.name} ({node.xid})
                </Text>
            ),
            key: key,
            data: dataNode,
            children: node.children ? transformToTreeData(node.children, key) : [],
        };
    });
};

// --- THIS IS THE FIX ---
const updateNodeByKey = (
    nodes: SchemaNode[],
    keyToUpdate: string,
    newValues: Partial<SchemaNode>,
    parentKey: string = 'root'
): SchemaNode[] => {
    return nodes.map((node, index) => {
        const currentKey = `${parentKey}-${node.type}-${node.xid}-${index}`;
        
        let newChildren = node.children;
        if (node.children) {
            newChildren = updateNodeByKey(node.children, keyToUpdate, newValues, currentKey);
        }

        if (currentKey === keyToUpdate) {
            return { ...node, ...newValues, children: newChildren };
        }

        return { ...node, children: newChildren };
    });
};

const countUnspecializedXidInTree = (
    nodes: SchemaNode[],
    xidToCount: string,
    schemaContent: SchemaFile | null,
    parentKey: string = 'root'
): number => {
    if (!schemaContent) return 0;

    let count = 0;

    for (const [index, node] of nodes.entries()) {
        const key = `${parentKey}-${node.type}-${node.xid}-${index}`;

        if (node.type === 'segment' && !node.definitionId && node.xid === xidToCount) {
            const potentialSpecializedId = `${node.xid}_${key.replace(/-/g, '_')}`;
            if (!schemaContent.segmentDefinitions[potentialSpecializedId]) {
                 count++;
            }
        }

        if (node.children) {
            count += countUnspecializedXidInTree(node.children, xidToCount, schemaContent, key);
        }
    }
    
    return count;
};

// --- THIS IS THE FIX ---
const findNodeByKey = (
    nodes: SchemaNode[], 
    keyToFind: string, 
    parentKey: string = 'root'
): SchemaNode | null => {
    for (const [index, node] of nodes.entries()) {
        const currentKey = `${parentKey}-${node.type}-${node.xid}-${index}`;
        if (currentKey === keyToFind) {
            return { ...node, key: currentKey };
        }
        if (node.children) {
            const found = findNodeByKey(node.children, keyToFind, currentKey);
            if (found) return found;
        }
    }
    return null;
}

const getEffectiveDefinitionId = (node: SchemaNode, schema: SchemaFile): string => {
    if (node.type !== 'segment') return node.xid;
    
    if (node.definitionId) {
        return node.definitionId;
    }
    
    const potentialSpecializedId = `${node.xid}_${node.key!.replace(/-/g, '_')}`;
    if (schema.segmentDefinitions && schema.segmentDefinitions[potentialSpecializedId]) {
        return potentialSpecializedId;
    }

    return node.xid;
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
        method: "get",
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
        if (!selectedNode || !selectedNode.key || !schemaContent || selectedNode.type !== 'segment') {
            return false;
        }
        
        if (selectedNode.definitionId) {
            return false;
        }

        const potentialSpecializedId = `${selectedNode.xid}_${selectedNode.key.replace(/-/g, '_')}`;
        if (schemaContent.segmentDefinitions[potentialSpecializedId]) {
            return false;
        }

        return countUnspecializedXidInTree(schemaContent.structure, selectedNode.xid, schemaContent) > 1;

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
                setSelectedNode(info.node.data);
                setIsEditing(false);
                setIsSharedEditingEnabled(false);
            }
        } else {
            setSelectedNode(null);
            setIsEditing(false);
            setIsSharedEditingEnabled(false);
        }
    };

    const handleSpecialize = () => {
        if (!selectedNode || !selectedNode.key) return;
        const originalDefId = selectedNode.definitionId || selectedNode.xid;
        const newDefId = `${originalDefId}_${selectedNode.key.replace(/-/g, "_")}`;

        setSchemaContent((currentContent) => {
            if (!currentContent) return null;
            const newContent = JSON.parse(JSON.stringify(currentContent));
            newContent.segmentDefinitions[newDefId] = { ...newContent.segmentDefinitions[originalDefId] };
            newContent.structure = updateNodeByKey(newContent.structure, selectedNode.key!, { definitionId: newDefId });
            return newContent;
        });

        setSelectedNode((currentNode) => ({ ...currentNode!, definitionId: newDefId }));
        setIsSharedEditingEnabled(false);
    };

    const handleCancelEditing = () => {
        setIsEditing(false);
        setIsSharedEditingEnabled(false);
        if (selectedNode) {
            const definitionId = selectedNode.definitionId || selectedNode.xid;
            const segmentDefinition = schemaContent?.segmentDefinitions[definitionId];
            form.setFieldsValue({ ...segmentDefinition, ...selectedNode });
        }
    };

    const handleSave = () => {
        form.validateFields().then((formValues) => {
            setSchemaContent(currentContent => {
                if (!selectedSchema || !currentContent || !selectedNode || !selectedNode.key) {
                    logger.error("Save aborted due to missing state.");
                    return currentContent;
                }
                
                logger.groupCollapsed(`[SAVE] Saving Node: ${selectedNode.key}`);
    
                const nodeInTree = findNodeByKey(currentContent.structure, selectedNode.key);
                if (!nodeInTree) {
                    logger.error(`Could not find node with key ${selectedNode.key} in the current schema structure.`);
                    logger.groupEnd();
                    return currentContent;
                }
    
                const definitionIdToUpdate = getEffectiveDefinitionId(nodeInTree, currentContent);
    
                const newContent = JSON.parse(JSON.stringify(currentContent));
                
                logger.debug("1. State at start of save:", {
                    nodeInTree: JSON.parse(JSON.stringify(nodeInTree)),
                    formValues: JSON.parse(JSON.stringify(formValues)),
                    definitionIdToUpdate: definitionIdToUpdate,
                });
    
                const segmentDef = newContent.segmentDefinitions[definitionIdToUpdate];
                if (segmentDef) {
                    segmentDef.name = formValues.name; 
                    if (formValues.elements) {
                        segmentDef.elements = formValues.elements;
                        segmentDef.elementsByXid = (formValues.elements || []).reduce((acc: any, el: any) => { acc[el.xid] = el; return acc; }, {});
                    }
                } else {
                     logger.error(`Could not find segment definition for ID: ${definitionIdToUpdate}`);
                     logger.groupEnd();
                     return currentContent;
                }
    
                const structuralNodeUpdate = {
                    name: formValues.name,
                    usage: formValues.usage,
                    repeat: nodeInTree.type === "loop" ? formValues.repeat : undefined,
                    max_use: nodeInTree.type === "segment" ? formValues.max_use : undefined,
                    ...(nodeInTree.definitionId ? { definitionId: nodeInTree.definitionId } : {}),
                };
                
                logger.debug("2. Structural update object:", structuralNodeUpdate);
                
                newContent.structure = updateNodeByKey(newContent.structure, nodeInTree.key!, structuralNodeUpdate);
    
                const cleanStructureForSave = (nodes: SchemaNode[]): SchemaNode[] => {
                    const deepCloneWithoutKey = (node: SchemaNode): SchemaNode => {
                        const { key, ...rest } = node;
                        return {
                            ...rest,
                            children: node.children ? node.children.map(deepCloneWithoutKey) : undefined,
                        };
                    };
                    return nodes.map(deepCloneWithoutKey);
                };
    
                const contentToSave = {
                    ...newContent,
                    structure: cleanStructureForSave(newContent.structure),
                };
    
                logger.debug("3. Final payload being sent to API:", JSON.parse(JSON.stringify(contentToSave)));
                logger.groupEnd();
                
                updateSchema({
                    resource: "schemas",
                    id: selectedSchema,
                    values: contentToSave,
                    successNotification: () => ({ message: "Schema saved successfully!", type: "success" }),
                    errorNotification: (error?: HttpError) => ({ message: `Save failed: ${error?.message || "Unknown error"}`, type: "error" }),
                    meta: {
                        onSuccess: () => {
                            setIsEditing(false);
                            setIsSharedEditingEnabled(false);
                            refetch();
                        },
                    },
                });
    
                return currentContent; 
            });
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

            <Layout style={{ background: "#fff" }}>
                <Sider width={500} style={{ background: "#fff", padding: "0 16px", borderRight: "1px solid #f0f0f0" }}>
                    <Space style={{ marginBottom: 8, display: "flex", justifyContent: "space-between" }}>
                        <Title level={5} style={{ margin: 0 }}>
                            Schema Structure
                        </Title>
                        <Space>
                            <Tooltip title="Expand All">
                                <Button size="small" icon={<PlusSquareOutlined />} onClick={() => setExpandedKeys(getAllKeys(treeData))} disabled={!treeData.length} />
                            </Tooltip>
                            <Tooltip title="Collapse All">
                                <Button size="small" icon={<MinusSquareOutlined />} onClick={() => setExpandedKeys([])} disabled={!treeData.length} />
                            </Tooltip>
                        </Space>
                    </Space>
                    {isTreeLoading && <Spin />}
                    {!isTreeLoading && treeData.length > 0 && <Tree showLine onExpand={onExpand} expandedKeys={expandedKeys} treeData={treeData} onSelect={handleSelect} />}
                    {!isTreeLoading && !selectedSchema && <Empty description="No schema selected" />}
                </Sider>
                <Content style={{ padding: "0 24px", minHeight: 280 }}>
                    <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", marginBottom: 16, height: "32px" }}>
                        {selectedNode && !isEditing && <Button icon={<EditOutlined />} onClick={() => setIsEditing(true)}>Edit</Button>}
                        {selectedNode && isEditing && (
                            <Space>
                                <Button icon={<CloseCircleOutlined />} onClick={handleCancelEditing}>Cancel</Button>
                                <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={isSaving}>Save</Button>
                            </Space>
                        )}
                    </div>

                    {selectedNode && schemaContent ? (
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
                        <Empty description="Select a node from the tree to see details." style={{ marginTop: 40 }} />
                    )}
                </Content>
            </Layout>
        </Card>
    );
};