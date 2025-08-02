import React, { useEffect, useState, useMemo } from "react";
import { useApiUrl, useCustom, useUpdate, useCreate, HttpError } from "@refinedev/core";
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
    theme,
    Modal,
    Input,
} from "antd";
import {
    SaveOutlined,
    PlusSquareOutlined,
    MinusSquareOutlined,
    EditOutlined,
    CloseCircleOutlined,
    CopyOutlined,
} from "@ant-design/icons";
import type { TreeProps } from "antd";
import { EditableNodeDetails } from "./EditableNodeDetails";
import { getAllKeys, transformToTreeData, findNodeByKey, updateNodeByKey } from "./schemaEditorUtils";
import { SchemaFile, SchemaListResponse, SchemaNode, SchemaTreeDataNode } from "./types";

const { Content, Sider } = Layout;
const { Title, Text } = Typography;

const getExpandedKeysToDepth = (
    nodes: SchemaNode[],
    maxDepth: number,
    currentDepth: number = 1,
    parentKey: string = "root"
): React.Key[] => {
    let keys: React.Key[] = [];
    if (currentDepth > maxDepth) {
        return keys;
    }
    nodes.forEach((node, index) => {
        if (node.type === "loop") {
            const key = `${parentKey}-${node.type}-${node.xid}-${index}`;
            keys.push(key);
            if (node.children) {
                keys = keys.concat(
                    getExpandedKeysToDepth(node.children, maxDepth, currentDepth + 1, key)
                );
            }
        }
    });
    return keys;
};

export const SchemaEditorList: React.FC = () => {
    const [form] = Form.useForm();
    const apiUrl = useApiUrl();
    const [selectedSchema, setSelectedSchema] = useState<string | null>(null);
    const [schemaContent, setSchemaContent] = useState<SchemaFile | null>(null);
    const [draftContent, setDraftContent] = useState<SchemaFile | null>(null);
    const [isPageInEditMode, setIsPageInEditMode] = useState(false);
    const [selectedNodeKey, setSelectedNodeKey] = useState<React.Key | null>(null);
    const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);
    const [isSpecializeModalVisible, setIsSpecializeModalVisible] = useState(false);
    const [newSchemaName, setNewSchemaName] = useState("");
    
    const { token } = theme.useToken();

    const { data: schemaFilesData, isLoading: isLoadingFiles, refetch: refetchSchemaList } = useCustom<SchemaListResponse>({
        url: `${apiUrl}/schemas`,
        method: "get",
    });

    const { data: schemaFileData, isLoading: isLoadingContent, refetch } = useCustom<SchemaFile>({
        url: `${apiUrl}/schemas/${selectedSchema}`,
        method: "get",
        queryOptions: { enabled: !!selectedSchema },
    });

    const { mutate: updateSchema, isLoading: isSaving } = useUpdate();
    const { mutate: createMutate, isLoading: isCreating } = useCreate();

    const [wasSaving, setWasSaving] = useState(false);

    useEffect(() => {
        if (wasSaving && !isSaving) {
            setIsPageInEditMode(false);
            setDraftContent(null);
            refetch();
        }
        setWasSaving(isSaving);
    }, [isSaving, wasSaving, refetch]);

    const isBaseSchemaSelected = useMemo(() => {
        if (!selectedSchema || !schemaFilesData?.data) return false;
        return schemaFilesData.data.base_schemas.includes(selectedSchema);
    }, [selectedSchema, schemaFilesData]);

    const schemaOptions = useMemo(() => {
        if (!schemaFilesData?.data) return [];
        const { base_schemas = [], specialized_schemas = [] } = schemaFilesData.data;
        const options = [];
        if (base_schemas.length > 0) {
            options.push({ label: "Base Schemas", options: base_schemas.map((f: string) => ({ label: f, value: f })) });
        }
        if (specialized_schemas.length > 0) {
            options.push({ label: "Specialized Schemas", options: specialized_schemas.map((f: string) => ({ label: f, value: f })) });
        }
        return options;
    }, [schemaFilesData]);

    const contentToShow = isPageInEditMode ? draftContent : schemaContent;
    
    const selectedNode = useMemo(() => {
        if (!selectedNodeKey || !contentToShow) return null;
        return findNodeByKey(contentToShow.structure, selectedNodeKey as string);
    }, [selectedNodeKey, contentToShow]);
    
    const treeData = useMemo(() => {
        if (!contentToShow) return [];
        return transformToTreeData(JSON.parse(JSON.stringify(contentToShow.structure)));
    }, [contentToShow]);

    useEffect(() => {
        if (schemaFileData?.data) {
            setSchemaContent(schemaFileData.data);
        } else {
            setSchemaContent(null);
        }
    }, [schemaFileData]);

    const handleSchemaSelectionChange = (value: string) => {
        setSelectedSchema(value);
        setIsPageInEditMode(false);
        setDraftContent(null);
        setSelectedNodeKey(null);
        form.resetFields();

        const isBase = schemaFilesData?.data?.base_schemas.includes(value);
        if (isBase) {
            setExpandedKeys([]);
        } else {
            setExpandedKeys([]);
        }
    };

    useEffect(() => {
        // --- THIS IS THE FIX ---
        // This effect now handles the initial expansion for ANY schema,
        // as long as its content has been loaded.
        if (schemaContent) {
            const initialKeys = getExpandedKeysToDepth(schemaContent.structure, 3);
            setExpandedKeys(initialKeys);
        } else {
            setExpandedKeys([]);
        }
    }, [schemaContent]); // This hook now only depends on the content itself.
    // --- END OF FIX ---

    const handleEnterEditMode = () => {
        if (schemaContent) {
            setDraftContent(JSON.parse(JSON.stringify(schemaContent)));
            setIsPageInEditMode(true);
        }
    };
    
    const handleCancelEditMode = () => {
        setDraftContent(null);
        setIsPageInEditMode(false);
        setSelectedNodeKey(null);
    };

    const handleSelect = (keys: React.Key[]) => {
        if (keys.length > 0) {
            setSelectedNodeKey(keys[0]);
        } else {
            setSelectedNodeKey(null);
        }
    };

    const handleOpenSpecializeModal = () => {
        if (!selectedSchema) return;
        const baseName = selectedSchema.replace(".json", "");
        setNewSchemaName(`${baseName}_custom.json`);
        setIsSpecializeModalVisible(true);
    };

    const handleSpecialize = () => {
        if (!selectedSchema || !newSchemaName) return;
        createMutate({
            resource: `schemas/${selectedSchema}/copy`,
            values: { new_name: newSchemaName },
            successNotification: (data) => ({
                message: "Schema Specialized!",
                description: `Successfully created ${data?.data.new_schema_name}. You can now select and edit it.`,
                type: "success",
            }),
            errorNotification: (error) => ({
                message: "Specialization Failed",
                description: error?.message || "Could not create specialized schema.",
                type: "error",
            }),
        }, {
            onSuccess: (data) => {
                setIsSpecializeModalVisible(false);
                setNewSchemaName("");
                refetchSchemaList();
                setSelectedSchema(data?.data.new_schema_name);
            },
        });
    };

    const handleSave = async () => {
        try {
            if (!selectedSchema || !draftContent) {
                throw new Error("Save aborted due to missing state. Please re-select the schema.");
            }
            const cleanStructureForSave = (nodes: SchemaNode[]): SchemaNode[] => {
                return nodes.map(({ key, ...rest }) => ({
                    ...rest,
                    children: rest.children ? cleanStructureForSave(rest.children) : undefined,
                }));
            };
            const contentToSave = { ...draftContent, structure: cleanStructureForSave(draftContent.structure) };
            updateSchema({
                resource: "schemas",
                id: selectedSchema,
                values: contentToSave,
                successNotification: () => ({ message: "Schema saved successfully!", type: "success" }),
                errorNotification: (error?: HttpError) => ({ message: `Save failed: ${error?.message || "Unknown error"}`, type: "error" }),
            });
        } catch (error) {
            const errorMessage = (error as Error)?.message || "An unknown error occurred.";
            notification.error({ message: "Save Failed", description: errorMessage });
        }
    };
    
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
                if (nodes[i].children && findAndRemove(nodes[i].children as SchemaTreeDataNode[], key)) {
                    return true;
                }
            }
            return false;
        };
        findAndRemove(data, dragNode.key);
        if (dragObj) {
            let ar: SchemaTreeDataNode[] = [];
            let i: number = -1;
            const findAndInsert = (nodes: SchemaTreeDataNode[], key: React.Key) => {
                for (let j = 0; j < nodes.length; j++) {
                    if (nodes[j].key === key) {
                        ar = nodes;
                        i = j;
                        return;
                    }
                    if (nodes[j].children) {
                        findAndInsert(nodes[j].children as SchemaTreeDataNode[], key);
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

    const onFormValuesChange = (_changedValues: any, allValues: any) => {
        if (!isPageInEditMode || !draftContent || !selectedNodeKey) return;
        setDraftContent(currentDraft => {
            if (!currentDraft) return null;
            const newDraft = JSON.parse(JSON.stringify(currentDraft));
            const nodeInTree = findNodeByKey(newDraft.structure, selectedNodeKey as string);
            if (!nodeInTree) {
                console.error(`Could not find node with key ${selectedNodeKey} to apply changes.`);
                return newDraft;
            }
            const contextId = nodeInTree.contextDefinitionId;
            if (contextId && newDraft.contextualDefinitions[contextId]) {
                const contextDef = newDraft.contextualDefinitions[contextId];
                contextDef.name = allValues.definition_name;
                const transformedElements = (allValues.elements || []).reduce((acc: any, el: any) => {
                    const newEl = { ...el };
                    if (Array.isArray(newEl.valid_codes)) {
                        newEl.valid_codes = newEl.valid_codes.map((code: string | number) => ({ code }));
                    }
                    acc[newEl.xid] = newEl;
                    return acc;
                }, {});
                contextDef.elements = transformedElements;
            }
            const structuralNodeUpdate = {
                name: allValues.structure_name,
                usage: allValues.usage,
                max_use: allValues.max_use,
            };
            const finalStructure = updateNodeByKey(newDraft.structure, selectedNodeKey as string, structuralNodeUpdate);
            return { ...newDraft, structure: finalStructure };
        });
    };

    const isTreeLoading = selectedSchema && isLoadingContent;

    return (
        <Card>
            <Card style={{ marginBottom: 16, minHeight: 70 }} bodyStyle={{padding: '16px 24px'}}>
                {contentToShow ? (
                    <>
                        <Title level={4} style={{ margin: 0 }}>{contentToShow.transactionName}</Title>
                        <Text type="secondary">Version: {contentToShow.version}</Text>
                    </>
                ) : (
                    <Spin spinning={!!(isLoadingFiles || isTreeLoading)}>
                        <div style={{ minHeight: 38 }} /> 
                    </Spin>
                )}
            </Card>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <Select
                    placeholder="Select a schema to edit"
                    loading={isLoadingFiles}
                    options={schemaOptions}
                    value={selectedSchema}
                    onChange={handleSchemaSelectionChange}
                    style={{ width: 300 }}
                />
                {selectedSchema && (
                    <Space>
                        {isBaseSchemaSelected && !isPageInEditMode && (
                            <Button icon={<CopyOutlined />} onClick={handleOpenSpecializeModal}>
                                Create Specialization
                            </Button>
                        )}
                        {!isBaseSchemaSelected && !isPageInEditMode && (
                            <Button icon={<EditOutlined />} onClick={handleEnterEditMode}>
                                Edit Schema
                            </Button>
                        )}
                        {isPageInEditMode && (
                             <>
                                <Button icon={<CloseCircleOutlined />} onClick={handleCancelEditMode}>Cancel</Button>
                                <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={isSaving}>Save Changes</Button>
                            </>
                        )}
                    </Space>
                )}
            </div>
            
            <Layout style={{ 
                background: "#fff",
                border: isPageInEditMode ? `2px solid ${token.colorPrimary}` : `2px solid transparent`,
                borderRadius: token.borderRadiusLG,
                transition: 'border-color 0.3s',
            }}>
                <Sider 
                    width={500} 
                    style={{ 
                        background: "#fff", 
                        padding: "16px",
                        borderRight: "1px solid #f0f0f0",
                        height: 'calc(100vh - 400px)',
                        overflowY: 'auto',
                    }}
                >
                    <Space style={{ marginBottom: 8, display: "flex", justifyContent: "space-between" }}>
                        <Title level={5} style={{ margin: 0 }}>Schema Structure</Title>
                        <Space>
                            <Tooltip title="Expand All"><Button size="small" icon={<PlusSquareOutlined />} onClick={() => setExpandedKeys(getAllKeys(treeData))} disabled={!treeData.length} /></Tooltip>
                            <Tooltip title="Collapse All"><Button size="small" icon={<MinusSquareOutlined />} onClick={() => setExpandedKeys([])} disabled={!treeData.length} /></Tooltip>
                        </Space>
                    </Space>
                    
                    {isTreeLoading && <Spin />}
                    {!isTreeLoading && treeData.length > 0 && 
                        <Tree showLine onExpand={setExpandedKeys} expandedKeys={expandedKeys} treeData={treeData} onSelect={handleSelect} selectedKeys={selectedNodeKey ? [selectedNodeKey] : []} draggable={isPageInEditMode} onDrop={handleDrop}/>
                    }
                    {!isTreeLoading && !selectedSchema && <Empty description="No schema selected" />}
                </Sider>
                <Content 
                    style={{ 
                        padding: "16px 24px", 
                        height: 'calc(100vh - 400px)',
                        overflowY: 'auto',
                    }}
                >
                     <Form form={form} onValuesChange={onFormValuesChange} name="schemaNodeForm">
                        <EditableNodeDetails
                            form={form}
                            isEditing={isPageInEditMode}
                            selectedNode={selectedNode}
                            schemaContent={contentToShow}
                            onUpdateSchema={setDraftContent}
                        />
                     </Form>
                </Content>
            </Layout>
            <Modal
                title="Create a Specialized Schema"
                open={isSpecializeModalVisible}
                onOk={handleSpecialize}
                onCancel={() => setIsSpecializeModalVisible(false)}
                confirmLoading={isCreating}
                okText="Create"
            >
                <p>This will create a new, editable copy of <strong>{selectedSchema}</strong>.</p>
                <Input
                    addonBefore="New file name:"
                    value={newSchemaName}
                    onChange={(e) => setNewSchemaName(e.target.value)}
                    placeholder="e.g., 837P_MyPartner_Custom.json"
                />
            </Modal>
        </Card>
    );
};