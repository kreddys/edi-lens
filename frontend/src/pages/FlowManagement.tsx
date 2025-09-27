import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from 'antd';
import { FlowsList } from './flows/FlowsList';
import FlowDetailPage from './flows/FlowDetailPage';
import FlowCreator from './flows/FlowCreator';
import FlowEditor from './flows/FlowEditor';

const { Content } = Layout;

/**
 * FlowManagement - Main component for flow-related operations
 * Handles nested routing for flows (list, create, edit, view)
 * Integrates template selection into the flow creation process
 */
const FlowManagement: React.FC = () => {
    return (
        <Layout style={{ minHeight: '100vh', backgroundColor: '#f5f5f5' }}>
            <Content style={{ padding: '24px' }}>
                <Routes>
                    {/* Default route - redirect to flows list */}
                    <Route path="/" element={<Navigate to="/flows" replace />} />
                    
                    {/* Flows list - main landing page */}
                    <Route path="/flows" element={<FlowsList />} />
                    
                    {/* Flow creation - integrated with template selection */}
                    <Route path="/flows/create" element={<FlowCreator />} />
                    
                    {/* Flow details - read-only view */}
                    <Route path="/flows/:id" element={<FlowDetailPage />} />
                    
                    {/* Flow editor - edit existing flow */}
                    <Route path="/flows/:id/edit" element={<FlowEditor />} />
                    
                    {/* Fallback for unmatched routes */}
                    <Route path="*" element={<Navigate to="/flows" replace />} />
                </Routes>
            </Content>
        </Layout>
    );
};

export default FlowManagement;