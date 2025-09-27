import React, { useState, useRef } from 'react';
import { Button, Space } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { FlowsList } from './FlowsList';
import { FlowDesigner } from './FlowDesigner';

export const FlowManagement: React.FC = () => {
  const [currentView, setCurrentView] = useState<'list' | 'designer' | 'edit'>('list');
  const [editingFlowId, setEditingFlowId] = useState<string | null>(null);
  const flowsListRef = useRef<any>(null);

  const handleCreateFlow = () => {
    setEditingFlowId(null);
    setCurrentView('designer');
  };

  const handleEditFlow = (flowId: string) => {
    setEditingFlowId(flowId);
    setCurrentView('edit');
  };

  const handleBackToList = () => {
    setEditingFlowId(null);
    setCurrentView('list');
    
    // Refresh the flows list when returning from designer
    if (flowsListRef.current && flowsListRef.current.refreshFlows) {
      flowsListRef.current.refreshFlows();
    }
  };

  if (currentView === 'designer' || currentView === 'edit') {
    return (
      <FlowDesigner 
        editingFlowId={editingFlowId}
        onBack={handleBackToList}
      />
    );
  }

  return (
    <div>
      {/* Action Bar */}
      <div style={{ 
        padding: '16px 24px', 
        borderBottom: '1px solid #f0f0f0',
        background: '#fff',
        display: 'flex',
        justifyContent: 'flex-end'
      }}>
        <Space>
          <Button 
            type="primary" 
            icon={<PlusOutlined />} 
            onClick={handleCreateFlow}
          >
            Create Flow
          </Button>
        </Space>
      </div>

      {/* Flows List */}
      <FlowsList ref={flowsListRef} onEditFlow={handleEditFlow} />
    </div>
  );
};