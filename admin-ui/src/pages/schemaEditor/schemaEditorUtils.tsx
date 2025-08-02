import { SchemaNode, SchemaTreeDataNode } from "./types";
import { Typography } from "antd";
import React from "react";

const { Text } = Typography;

export const getAllKeys = (nodes: SchemaTreeDataNode[]): React.Key[] => {
    let keys: React.Key[] = [];
    for (const node of nodes) {
        if (node.key) keys.push(node.key);
        if (node.children) {
            keys = keys.concat(getAllKeys(node.children as SchemaTreeDataNode[]));
        }
    }
    return keys;
};

export const transformToTreeData = (nodes: SchemaNode[], parentKey: string = "root"): SchemaTreeDataNode[] => {
    return nodes.map((node, index) => {
        const key = `${parentKey}-${node.type}-${node.xid}-${index}`;
        const dataNode = { ...node, key };
        return {
            title: <Text><Text strong>{node.type === "loop" ? "Loop: " : ""}</Text>{node.name} ({node.xid})</Text>,
            key: key,
            data: dataNode,
            children: node.children ? transformToTreeData(node.children, key) : [],
        };
    });
};

export const updateNodeByKey = (
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

export const findNodeByKey = (nodes: SchemaNode[], keyToFind: string, parentKey: string = 'root'): SchemaNode | null => {
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