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
    notification,
    Alert,
} from "antd";
import {
    SaveOutlined,
    PlusSquareOutlined,
    MinusSquareOutlined,
    EditOutlined,
    CloseCircleOutlined,
} from "@ant-design/icons";
import type { TreeDataNode, TreeProps } from "antd";
import { EditableNodeDetails, getEffectiveDefinitionId } from "./EditableNodeDetails";
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

interface SchemaTreeDataNode extends TreeDataNode {
    data: SchemaNode;
    children?: SchemaTreeDataNode[];
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

const transformToTreeData = (nodes: SchemaNode[], parentKey: string = "root"): SchemaTreeDataNode[] => {
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

export const SchemaEditorList: React.FC = () => {
    const [form] = Form.useForm();
    const apiUrl = useApiUrl();
    const [selectedSchema, setSelectedSchema] = useState<string | null>(null);
    const [schemaContent, setSchemaContent] = useState<SchemaFile | null>(null);
    const [draftContent, setDraftContent] = useState<SchemaFile | null>(null);
    const [isPageInEditMode, setIsPageInEditMode] = useState(false);
    const [selectedNode, setSelectedNode] = useState<SchemaNode | null>(null);
    const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);
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

    const contentToShow = isPageInEditMode ? draftContent : schemaContent;

    const treeData = useMemo(() => {
        if (!contentToShow) return [];
        const structureCopy = JSON.parse(JSON.stringify(contentToShow.structure));
        return transformToTreeData(structureCopy);
    }, [contentToShow]);

    const isShared = useMemo(() => {
        if (!selectedNode || !selectedNode.key || !contentToShow || selectedNode.type !== 'segment') {
            return false;
        }
        
        if (selectedNode.definitionId) {
            return false;
        }

        const potentialSpecializedId = `${selectedNode.xid}_${selectedNode.key.replace(/-/g, '_')}`;
        if (contentToShow.segmentDefinitions[potentialSpecializedId]) {
            return false;
        }

        return countUnspecializedXidInTree(contentToShow.structure, selectedNode.xid, contentToShow) > 1;

    }, [selectedNode, contentToShow]);


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
        setIsSharedEditingEnabled(false);
        form.resetFields();
    }, [selectedSchema, form, isPageInEditMode]);

    const handleEnterEditMode = () => {
        if (schemaContent) {
            setDraftContent(JSON.parse(JSON.stringify(schemaContent)));
            setIsPageInEditMode(true);
        }
    };
    
    const handleCancelEditMode = () => {
        setDraftContent(null);
        setIsPageInEditMode(false);
        setSelectedNode(null);
    };

    const onExpand = (keys: React.Key[]) => setExpandedKeys(keys);

    const handleSelect = (selectedKeys: React.Key[], info: any) => {
        if (selectedKeys.length > 0 && info.node.data) {
            if (selectedNode?.key !== info.node.data.key) {
                setSelectedNode(info.node.data);
                setIsSharedEditingEnabled(false);
            }
        } else {
            setSelectedNode(null);
            setIsSharedEditingEnabled(false);
        }
    };

    const handleSpecialize = () => {
        logger.groupCollapsed("[SPECIALIZE]");
        try {
            if (!selectedNode || !selectedNode.key) {
                logger.error("Specialize failed: No node selected.");
                return;
            }

            const originalDefId = selectedNode.definitionId || selectedNode.xid;
            const newDefId = `${originalDefId}_${selectedNode.key.replace(/-/g, "_")}`;
            logger.debug("New specialized definition ID:", newDefId);

            setDraftContent((currentContent) => {
                if (!currentContent) return null;
                const newContent = JSON.parse(JSON.stringify(currentContent));
                const definitionToCopy = newContent.segmentDefinitions[originalDefId];
                
                newContent.segmentDefinitions[newDefId] = JSON.parse(JSON.stringify(definitionToCopy));
                
                newContent.structure = updateNodeByKey(newContent.structure, selectedNode.key!, { definitionId: newDefId });
                
                setSelectedNode((currentNode) => ({ ...currentNode!, definitionId: newDefId }));
                
                return newContent;
            });

            setIsSharedEditingEnabled(false);
            notification.success({ message: "Segment specialized successfully." });
        } catch (error) {
            logger.error("An error occurred during specialization:", error);
            notification.error({ message: "Failed to specialize segment." });
        } finally {
            logger.groupEnd();
        }
    };

    const handleSave = async () => {
        logger.groupCollapsed(`[SAVE]`);
        try {
            // No need to validate here anymore, as data is always up-to-date in draftContent
            if (!selectedSchema || !draftContent) {
                throw new Error("Save aborted due to missing state. Please re-select the schema.");
            }
            
            logger.debug("1. Content at start of save:", JSON.parse(JSON.stringify(draftContent)));
            
            const cleanStructureForSave = (nodes: SchemaNode[]): SchemaNode[] => {
                return nodes.map(({ key, ...rest }) => ({
                    ...rest,
                    children: rest.children ? cleanStructureForSave(rest.children) : undefined,
                }));
            };
    
            const contentToSave = { ...draftContent, structure: cleanStructureForSave(draftContent.structure) };
            logger.debug("2. Final payload being sent to API:", JSON.parse(JSON.stringify(contentToSave)));
            
            updateSchema({
                resource: "schemas",
                id: selectedSchema,
                values: contentToSave,
                successNotification: () => ({ message: "Schema saved successfully!", type: "success" }),
                errorNotification: (error?: HttpError) => ({ message: `Save failed: ${error?.message || "Unknown error"}`, type: "error" }),
                meta: {
                    onSuccess: () => {
                        setIsPageInEditMode(false);
                        setDraftContent(null);
                        refetch(); 
                    },
                },
            });
    
        } catch (error) {
            const errorMessage = (error as Error)?.message || "An unknown error occurred.";
            logger.error("An error occurred during save:", error);
            notification.error({ message: "Save Failed", description: errorMessage });
        } finally {
            logger.groupEnd();
        }
    };
    
    // --- THIS IS THE NEW FUNCTION TO HANDLE REAL-TIME UPDATES ---
    const onFormValuesChange = (changedValues: any, allValues: any) => {
        if (!isPageInEditMode || !draftContent || !selectedNode) return;
        
        logger.groupCollapsed('[FORM CHANGE]');
        logger.debug("Changed values:", changedValues);

        const keyToUpdate = selectedNode.key!;
        const newDraft = JSON.parse(JSON.stringify(draftContent));
        const nodeInTree = findNodeByKey(newDraft.structure, keyToUpdate);
        
        if (!nodeInTree) {
            logger.error(`Could not find node with key ${keyToUpdate} to apply changes.`);
            logger.groupEnd();
            return;
        }

        const definitionIdToUpdate = getEffectiveDefinitionId(nodeInTree, newDraft);

        // Update definition properties
        const segmentDef = newDraft.segmentDefinitions[definitionIdToUpdate];
        if (segmentDef) {
            if ('definition_name' in changedValues) {
                segmentDef.name = changedValues.definition_name;
            }
            if ('elements' in changedValues) {
                segmentDef.elements = allValues.elements;
                segmentDef.elementsByXid = (allValues.elements || []).reduce((acc: any, el: any) => { acc[el.xid] = el; return acc; }, {});
            }
        }

        // Update structure properties
        if('structure_name' in changedValues) nodeInTree.name = changedValues.structure_name;
        if('usage' in changedValues) nodeInTree.usage = changedValues.usage;
        if('repeat' in changedValues) nodeInTree.repeat = changedValues.repeat;
        if('max_use' in changedValues) nodeInTree.max_use = changedValues.max_use;

        setDraftContent(newDraft);
        logger.debug("Updated draft content:", newDraft);
        logger.groupEnd();
    };
    
    // --- THIS IS THE FINAL, CORRECTED DRAG-AND-DROP HANDLER ---
    const handleDrop: TreeProps<SchemaTreeDataNode>['onDrop'] = (info) => {
        const { dragNode, node: dropTargetNode, dropToGap } = info;
    
        if (!dropToGap) {
            notification.warning({ message: "Dropping inside another node is not supported." });
            return;
        }
        if (!draftContent) return;
    
        const data = [...treeData];
    
        let dragObj: SchemaTreeDataNode | undefined;
    
        const findAndRemove = (nodes: SchemaTreeDataNode[], key: React.Key): boolean => {
            for (let i = 0; i < nodes.length; i++) {
                if (nodes[i].key === key) {
                    [dragObj] = nodes.splice(i, 1);
                    return true;
                }
                // --- FIX: Add guard clause before recursion ---
                if (nodes[i].children && findAndRemove(nodes[i].children!, key)) {
                    return true;
                }
            }
            return false;
        };
    
        findAndRemove(data, dragNode.key);
    
        if (dragObj) {
            let ar: SchemaTreeDataNode[] | undefined;
            let i: number = -1;
    
            const findAndInsert = (nodes: SchemaTreeDataNode[], key: React.Key) => {
                for (let j = 0; j < nodes.length; j++) {
                    if (nodes[j].key === key) {
                        ar = nodes;
                        i = j;
                        return;
                    }
                    // --- FIX: Add guard clause before recursion ---
                    if (nodes[j].children) {
                        findAndInsert(nodes[j].children!, key);
                    }
                }
            };
    
            findAndInsert(data, dropTargetNode.key);
    
            const dragParentPos = dragNode.pos.substring(0, dragNode.pos.lastIndexOf('-'));
            const dropParentPos = dropTargetNode.pos.substring(0, dropTargetNode.pos.lastIndexOf('-'));
    
            if(dragParentPos !== dropParentPos) {
                 notification.warning({ message: "Moving nodes between different parents is not yet supported." });
                 return;
            }
    
            if (ar && i > -1) {
                 const dropPos = info.dropPosition - Number(dropTargetNode.pos.split('-').pop());
                 const isBelow = dropPos > 0;
                 if (isBelow) {
                    ar.splice(i + 1, 0, dragObj);
                } else {
                    ar.splice(i, 0, dragObj);
                }
            }
        }
    
        const convertTreeToSchema = (nodes: SchemaTreeDataNode[]): SchemaNode[] => {
            return nodes.map(node => {
                const schemaNode: SchemaNode = { ...node.data };
                if (node.children && node.children.length > 0) {
                    schemaNode.children = convertTreeToSchema(node.children as SchemaTreeDataNode[]);
                } else {
                    delete schemaNode.children;
                }
                delete schemaNode.key;
                return schemaNode;
            });
        };
    
        setDraftContent({
            ...draftContent,
            structure: convertTreeToSchema(data),
        });
    };

    const isTreeLoading = selectedSchema && isLoadingContent;

    return (
        <Card>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <Select
                    placeholder="Select a schema to edit"
                    loading={isLoadingFiles}
                    options={schemaFilesData?.data.map((f: string) => ({ label: f, value: f }))}
                    onChange={(value) => {
                        setSelectedSchema(value);
                        setIsPageInEditMode(false);
                        setDraftContent(null);
                    }}
                    style={{ width: 300 }}
                />
                {selectedSchema && (
                    <Space>
                        {!isPageInEditMode ? (
                            <Button icon={<EditOutlined />} onClick={handleEnterEditMode}>Edit Schema</Button>
                        ) : (
                            <>
                                <Button icon={<CloseCircleOutlined />} onClick={handleCancelEditMode}>Cancel</Button>
                                <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={isSaving}>Save Schema</Button>
                            </>
                        )}
                    </Space>
                )}
            </div>

            {isPageInEditMode && <Alert message="Edit Mode" type="info" showIcon style={{ marginBottom: 16 }} description="You are in edit mode. All changes to structure and properties will be saved when you click 'Save Schema'." />}

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
                    {!isTreeLoading && treeData.length > 0 && 
                        <Tree 
                            showLine 
                            onExpand={onExpand} 
                            expandedKeys={expandedKeys} 
                            treeData={treeData} 
                            onSelect={handleSelect}
                            draggable={isPageInEditMode ? { icon: false } : false} 
                            onDrop={handleDrop}
                        />
                    }
                    {!isTreeLoading && !selectedSchema && <Empty description="No schema selected" />}
                </Sider>
                <Content style={{ padding: "0 24px", minHeight: 280 }}>
                    {selectedNode && contentToShow ? (
                        <EditableNodeDetails
                            form={form}
                            isEditing={isPageInEditMode}
                            selectedNode={selectedNode}
                            schemaContent={contentToShow}
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