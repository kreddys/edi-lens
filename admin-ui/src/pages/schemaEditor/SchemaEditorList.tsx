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
import type { TreeProps } from "antd";
import { EditableNodeDetails } from "./EditableNodeDetails";
import { getAllKeys, transformToTreeData, findNodeByKey } from "./schemaEditorUtils.tsx";
import { SchemaFile, SchemaListResponse, SchemaNode, SchemaTreeDataNode } from "./types";

const { Content, Sider } = Layout;
const { Title, Text } = Typography;

export const SchemaEditorList: React.FC = () => {
    const [form] = Form.useForm();
    const apiUrl = useApiUrl();
    const [selectedSchema, setSelectedSchema] = useState<string | null>(null);
    const [schemaContent, setSchemaContent] = useState<SchemaFile | null>(null);
    const [draftContent, setDraftContent] = useState<SchemaFile | null>(null);
    const [isPageInEditMode, setIsPageInEditMode] = useState(false);
    const [selectedNodeKey, setSelectedNodeKey] = useState<React.Key | null>(null);
    const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);

    const { data: schemaFilesData, isLoading: isLoadingFiles } = useCustom<SchemaListResponse>({
        url: `${apiUrl}/schemas`,
        method: "get",
    });

    const { data: schemaFileData, isLoading: isLoadingContent, refetch } = useCustom<SchemaFile>({
        url: `${apiUrl}/schemas/${selectedSchema}`,
        method: "get",
        queryOptions: { enabled: !!selectedSchema },
    });

    const { mutate: updateSchema, isLoading: isSaving } = useUpdate();

    const schemaOptions = useMemo(() => {
        if (!schemaFilesData?.data) return [];
        const { base_schemas = [], specialized_schemas = [] } = schemaFilesData.data;
        const options = [];
        if (base_schemas.length > 0) {
            // --- FIX: Add explicit 'string' type to map parameter ---
            options.push({ label: "Base Schemas", options: base_schemas.map((f: string) => ({ label: f, value: f })) });
        }
        if (specialized_schemas.length > 0) {
            // --- FIX: Add explicit 'string' type to map parameter ---
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
            const topLevelTreeData = transformToTreeData(JSON.parse(JSON.stringify(schemaFileData.data.structure)));
            if (topLevelTreeData.length > 0 && topLevelTreeData[0].key) {
                setExpandedKeys([]);
            }
        } else {
            setSchemaContent(null);
            setExpandedKeys([]);
        }
    }, [schemaFileData]);

    useEffect(() => {
        setSelectedNodeKey(null);
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
        setSelectedNodeKey(null);
    };

    const handleSelect = (selectedKeys: React.Key[]) => {
        if (selectedKeys.length > 0) {
            setSelectedNodeKey(selectedKeys[0]);
        } else {
            setSelectedNodeKey(null);
        }
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
                meta: {
                    onSuccess: () => {
                        setIsPageInEditMode(false);
                        setDraftContent(null);
                        setSelectedNodeKey(null);
                        refetch(); 
                    },
                },
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

    const isTreeLoading = selectedSchema && isLoadingContent;

    return (
        <Card>
            {contentToShow && (
                 <Card style={{ marginBottom: 16 }} bodyStyle={{padding: '16px 24px'}}>
                    <Title level={4} style={{ margin: 0 }}>{contentToShow.transactionName}</Title>
                    <Text type="secondary">Version: {contentToShow.version}</Text>
                </Card>
            )}

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <Select
                    placeholder="Select a schema to edit"
                    loading={isLoadingFiles}
                    options={schemaOptions}
                    value={selectedSchema}
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
            
            <Layout style={{ background: "#fff", minHeight: '65vh' }}>
                <Sider width={500} style={{ background: "#fff", padding: "0 16px", borderRight: "1px solid #f0f0f0", overflow: 'auto' }}>
                    <Space style={{ marginBottom: 8, display: "flex", justifyContent: "space-between" }}>
                        <Title level={5} style={{ margin: 0 }}>Schema Structure</Title>
                        <Space>
                            <Tooltip title="Expand All"><Button size="small" icon={<PlusSquareOutlined />} onClick={() => setExpandedKeys(getAllKeys(treeData))} disabled={!treeData.length} /></Tooltip>
                            <Tooltip title="Collapse All"><Button size="small" icon={<MinusSquareOutlined />} onClick={() => setExpandedKeys([])} disabled={!treeData.length} /></Tooltip>
                        </Space>
                    </Space>
                    {isTreeLoading && <Spin />}
                    {!isTreeLoading && treeData.length > 0 && 
                        <Tree showLine onExpand={setExpandedKeys} expandedKeys={expandedKeys} treeData={treeData} onSelect={handleSelect} selectedKeys={selectedNodeKey ? [selectedNodeKey] : []} draggable={isPageInEditMode ? { icon: false } : false} onDrop={handleDrop}/>
                    }
                    {!isTreeLoading && !selectedSchema && <Empty description="No schema selected" />}
                </Sider>
                <Content style={{ padding: "0 24px", overflow: 'auto', flex: 1 }}>
                     <EditableNodeDetails
                        form={form}
                        isEditing={isPageInEditMode}
                        selectedNode={selectedNode}
                        schemaContent={contentToShow}
                        onUpdateSchema={setDraftContent}
                    />
                </Content>
            </Layout>
        </Card>
    );
};