import React, { useState, useEffect } from 'react';
import { Card, Table, Button, Space, notification, Typography } from 'antd';
import { flowAPI } from '../providers/data';

const { Title } = Typography;

interface Template {
  id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  processor_count: number;
  connection_count: number;
  parameter_count: number;
  usage_count: number;
}

export const TemplatesPage: React.FC = () => {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const response = await flowAPI.listTemplates();
      setTemplates(response.templates || []);
      notification.success({
        message: 'Templates Loaded',
        description: `Found ${response.templates?.length || 0} templates using V1 API`
      });
    } catch (error) {
      console.error('Failed to load templates:', error);
      notification.error({
        message: 'Error',
        description: 'Failed to load templates from V1 API'
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTemplates();
  }, []);

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: 'Category',
      dataIndex: 'category',
      key: 'category',
    },
    {
      title: 'Processors',
      dataIndex: 'processor_count',
      key: 'processor_count',
    },
    {
      title: 'Connections',
      dataIndex: 'connection_count',
      key: 'connection_count',
    },
    {
      title: 'Parameters',
      dataIndex: 'parameter_count',
      key: 'parameter_count',
    },
    {
      title: 'Usage',
      dataIndex: 'usage_count',
      key: 'usage_count',
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (record: Template) => (
        <Space>
          <Button onClick={() => console.log('Use template:', record.id)}>
            Use Template
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>Flow Templates (V1 API)</Title>
      <Card>
        <div style={{ marginBottom: '16px' }}>
          <Button type="primary" onClick={loadTemplates} loading={loading}>
            Refresh Templates
          </Button>
        </div>
        <Table
          columns={columns}
          dataSource={templates}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
        />
      </Card>
    </div>
  );
};