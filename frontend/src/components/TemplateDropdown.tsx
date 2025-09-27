import React, { useState, useEffect } from 'react';
import { Select, Space, Tag, Alert } from 'antd';
import axiosInstance from '../providers/axios';
const { Option } = Select;

interface Template {
  id: string;
  name: string;
  description: string;
  filename: string;
  processor_count: number;
  connection_count: number;
  parameter_count: number;
  has_parameters: boolean;
  processors: string[];
}

interface TemplateDropdownProps {
  onTemplateSelect: (templateData: any) => void;
  disabled?: boolean;
}

export const TemplateDropdown: React.FC<TemplateDropdownProps> = ({
  onTemplateSelect,
  disabled = false
}) => {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    setLoading(true);
    setError('');
    
    try {
      const response = await axiosInstance.get('/api/flows/templates/');
      setTemplates(response.data);
    } catch (err: any) {
      console.error('Failed to load templates:', err);
      setError('Failed to load templates');
    } finally {
      setLoading(false);
    }
  };

  const handleTemplateSelect = async (templateId: string) => {
    if (!templateId) {
      setSelectedTemplate('');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await axiosInstance.get(`/api/flows/templates/${templateId}`);
      const templateData = response.data.template_data;
      
      // Call the parent callback with the template data
      onTemplateSelect(templateData);
      
      // Keep selection to show what was loaded
      setSelectedTemplate(templateId);
    } catch (err: any) {
      console.error('Failed to load template:', err);
      setError('Failed to load template');
      setSelectedTemplate('');
    } finally {
      setLoading(false);
    }
  };

  const renderTemplateOption = (template: Template) => {
    return (
      <Option key={template.id} value={template.id} label={template.name}>
        <div style={{ padding: '4px 0' }}>
          <div style={{ fontWeight: 500, marginBottom: '4px' }}>
            {template.name}
          </div>
          <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>
            {template.description}
          </div>
          <Space size={4}>
            <Tag color="blue">
              {template.processor_count} processors
            </Tag>
            <Tag color="green">
              {template.connection_count} connections
            </Tag>
            {template.has_parameters && (
              <Tag color="orange">
                {template.parameter_count} parameters
              </Tag>
            )}
          </Space>
        </div>
      </Option>
    );
  };

  if (error) {
    return (
      <Alert 
        message={error} 
        type="error" 
        showIcon 
        style={{ minWidth: '200px' }}
      />
    );
  }

  return (
    <Select
      value={selectedTemplate}
      onChange={handleTemplateSelect}
      placeholder="Load template..."
      style={{ minWidth: '200px' }}
      loading={loading}
      disabled={disabled || loading}
      optionLabelProp="label"
      dropdownStyle={{ maxHeight: '300px' }}
      allowClear
    >
      {templates.map(renderTemplateOption)}
    </Select>
  );
};