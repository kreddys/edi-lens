import React from "react";
import { Descriptions, Typography, Alert, Divider } from "antd";

const { Title } = Typography;

interface ReadOnlyNodeDetailsProps {
    selectedNode: any;
    schemaContent: any;
    isShared: boolean;
}

export const ReadOnlyNodeDetails: React.FC<ReadOnlyNodeDetailsProps> = ({
    selectedNode,
    schemaContent,
    isShared,
}) => {
    if (!selectedNode) return null;

    const segmentDefinition = schemaContent.segmentDefinitions[selectedNode.xid];

    return (
        <div>
            <Title level={5} style={{ marginBottom: 24 }}>Node Details: {selectedNode.name} ({selectedNode.xid})</Title>
            
            <Divider orientation="left" plain>Structure Properties</Divider>
            {/* --- FIX: Added column prop for alignment --- */}
            <Descriptions bordered column={1} size="small" labelStyle={{ width: '200px' }}>
                <Descriptions.Item label="Display Name">{selectedNode.name}</Descriptions.Item>
                <Descriptions.Item label="Usage">{selectedNode.usage}</Descriptions.Item>
                {selectedNode.type === 'loop' && <Descriptions.Item label="Repeat">{selectedNode.repeat}</Descriptions.Item>}
                {selectedNode.type === 'segment' && <Descriptions.Item label="Max Use">{selectedNode.max_use}</Descriptions.Item>}
            </Descriptions>

            {selectedNode.type === "segment" && (
                <>
                    <Divider orientation="left" plain>Segment Definition</Divider>
                    {segmentDefinition ? (
                        <>
                            {isShared && (
                                <Alert 
                                    message="This is a shared segment definition."
                                    type="info" 
                                    showIcon 
                                    style={{marginBottom: 16}}
                                />
                            )}
                            <Descriptions bordered column={1} size="small" labelStyle={{ width: '200px' }}>
                                <Descriptions.Item label="Definition Name">{segmentDefinition.name}</Descriptions.Item>
                            </Descriptions>
                        </>
                    ) : (
                        <Alert 
                            message="Unlinked Segment"
                            description="This segment is not linked to a definition."
                            type="warning" 
                            showIcon 
                        />
                    )}
                </>
            )}
        </div>
    );
};