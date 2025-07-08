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
    Descriptions,
    Tooltip,
} from "antd";
// --- NEW ICONS ---
import {
    SaveOutlined,
    PlusSquareOutlined,
    MinusSquareOutlined,
} from "@ant-design/icons";
import type { TreeDataNode } from 'antd';

const { Content, Sider } = Layout;
const { Title, Text } = Typography;

interface SchemaNode {
    type: 'loop' | 'segment';
    xid: string;
    name: string;
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

export const SchemaEditorList: React.FC = () => {
    const apiUrl = useApiUrl();
    const [selectedSchema, setSelectedSchema] = useState<string | null>(null);
    const [schemaContent, setSchemaContent] = useState<SchemaFile | null>(null);
    const [selectedNode, setSelectedNode] = useState<SchemaNode | null>(null);
    const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);

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
        if (!schemaFileData?.data) return [];
        return transformToTreeData(schemaFileData.data.structure);
    }, [schemaFileData]);
    
    useEffect(() => {
        if (schemaFileData?.data) {
            setSchemaContent(schemaFileData.data);
            // On new data, only expand the first level of nodes
            setExpandedKeys(treeData.map(node => node.key));
        } else {
            setSchemaContent(null);
            setExpandedKeys([]); // Clear keys if no data
        }
    }, [schemaFileData, treeData]);

    useEffect(() => {
        setSelectedNode(null);
    }, [selectedSchema]);

    const onExpand = (keys: React.Key[]) => {
        setExpandedKeys(keys);
    };

    const handleSelect = (selectedKeys: React.Key[], info: any) => {
        if (selectedKeys.length > 0 && info.node.data) {
            setSelectedNode(info.node.data);
        } else {
            setSelectedNode(null);
        }
    };

    const handleSave = () => {
        if (selectedSchema && schemaContent) {
            updateSchema({
                resource: "schemas",
                id: selectedSchema,
                values: schemaContent,
                successNotification: () => ({ message: "Schema saved successfully!", type: "success" }),
                errorNotification: (error?: HttpError) => ({ message: `Save failed: ${error?.message || 'Unknown error'}`, type: "error" }),
            });
        }
    };

    const isTreeLoading = selectedSchema && isLoadingContent;

    return (
        <Card>
            <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
                <Select
                    placeholder="Select a schema to edit"
                    loading={isLoadingFiles}
                    options={schemaFilesData?.data.map((f: string) => ({ label: f, value: f }))}
                    onChange={(value) => setSelectedSchema(value)}
                    style={{ width: 300 }}
                />
                <Button 
                    type="primary" 
                    icon={<SaveOutlined />} 
                    onClick={handleSave}
                    loading={isSaving}
                    disabled={!selectedSchema || !schemaContent}
                >
                    Save Schema
                </Button>
            </Space>

            <Layout style={{ background: '#fff' }}>
                <Sider width={500} style={{ background: '#fff', padding: '0 16px', borderRight: '1px solid #f0f0f0' }}>
                    <Space style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between' }}>
                        <Title level={5} style={{ margin: 0 }}>Schema Structure</Title>
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
                    <Title level={5}>Selected Node Details</Title>
                    {selectedNode ? (
                        <Descriptions bordered column={1} size="small">
                            <Descriptions.Item label="Type">{selectedNode.type}</Descriptions.Item>
                            <Descriptions.Item label="XID">{selectedNode.xid}</Descriptions.Item>
                            <Descriptions.Item label="Name">{selectedNode.name}</Descriptions.Item>
                            <Descriptions.Item label="Usage">{selectedNode.usage}</Descriptions.Item>
                            <Descriptions.Item label="Position">{selectedNode.pos}</Descriptions.Item>
                            {selectedNode.type === 'loop' && <Descriptions.Item label="Repeat">{selectedNode.repeat}</Descriptions.Item>}
                            {selectedNode.type === 'segment' && <Descriptions.Item label="Max Use">{selectedNode.max_use}</Descriptions.Item>}
                        </Descriptions>
                    ) : (
                        <Empty description="Select a node from the tree to see details." />
                    )}
                </Content>
            </Layout>
        </Card>
    );
};