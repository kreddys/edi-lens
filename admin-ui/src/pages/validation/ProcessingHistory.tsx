import React, { useState } from "react";
import {
  Card,
  Table,
  Button,
  Space,
  Select,
  DatePicker,
  Tag,
  Typography,
  Row,
  Col,
  Statistic,
  Progress,
  Alert,
  Modal,
  Descriptions
} from "antd";
import {
  DownloadOutlined,
  EyeOutlined,
  ReloadOutlined,
  ExportOutlined,
  ApiOutlined,
  CloudServerOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  ClockCircleOutlined
} from "@ant-design/icons";
import { useList } from "@refinedev/core";
import type { ColumnsType } from "antd/es/table";

const { RangePicker } = DatePicker;
const { Title, Text } = Typography;

interface ProcessingLogEntry {
  id: number;
  timestamp: string;
  source: "API" | "SFTP";
  file_name?: string;
  validation_result: "VALID" | "INVALID" | "ERROR";
  processing_time_ms: number;
  error_count: number;
  schema_used?: string;
  snip_level_used?: string;
  matched_profile?: string;
  ta1_generated: boolean;
  ta1_999_generated: boolean;
}

interface ProcessingMetrics {
  success_rate: number;
  avg_processing_time: number;
  total_processed: number;
  volume_by_day: Array<{ date: string; count: number }>;
  common_errors: Array<{ error: string; count: number }>;
  schema_usage: Array<{ schema: string; count: number }>;
}

export const ProcessingHistory: React.FC = () => {
  const [selectedFilters, setSelectedFilters] = useState<{
    source?: "API" | "SFTP";
    result?: "VALID" | "INVALID" | "ERROR";
    dateRange?: [string, string];
  }>({});
  const [selectedRecord, setSelectedRecord] = useState<ProcessingLogEntry | null>(null);
  const [detailsVisible, setDetailsVisible] = useState(false);

  // Fetch processing logs with filters
  const { data: logsData, isLoading } = useList<ProcessingLogEntry>({
    resource: "processing-logs",
    filters: Object.entries(selectedFilters)
      .filter(([_, value]) => value !== undefined)
      .map(([field, value]) => ({
        field,
        operator: "eq" as const,
        value,
      })),
    pagination: {
      current: 1,
      pageSize: 50,
    },
    sorters: [
      {
        field: "timestamp",
        order: "desc",
      },
    ],
  });

  const logs = logsData?.data || [];

  // Mock metrics calculation - in real implementation, this would be a separate API call
  const metrics: ProcessingMetrics = {
    success_rate: logs.length > 0 ? (logs.filter(log => log.validation_result === "VALID").length / logs.length) * 100 : 0,
    avg_processing_time: logs.length > 0 ? logs.reduce((sum, log) => sum + log.processing_time_ms, 0) / logs.length : 0,
    total_processed: logs.length,
    volume_by_day: [], // Would be calculated from actual data
    common_errors: [
      { error: "Invalid ISA segment", count: 5 },
      { error: "Missing required element", count: 3 },
      { error: "Invalid date format", count: 2 }
    ],
    schema_usage: [
      { schema: "837.5010.X222.A1.json", count: 45 },
      { schema: "835.5010.X221.A1.json", count: 12 },
      { schema: "270.5010.X279.A1.json", count: 8 }
    ]
  };

  const columns: ColumnsType<ProcessingLogEntry> = [
    {
      title: "Timestamp",
      dataIndex: "timestamp",
      key: "timestamp",
      width: 180,
      render: (timestamp: string) => (
        <Text style={{ fontSize: "12px" }}>
          {new Date(timestamp).toLocaleString()}
        </Text>
      ),
    },
    {
      title: "Source",
      dataIndex: "source",
      key: "source",
      width: 80,
      render: (source: "API" | "SFTP") => (
        <Tag 
          icon={source === "API" ? <ApiOutlined /> : <CloudServerOutlined />}
          color={source === "API" ? "blue" : "green"}
        >
          {source}
        </Tag>
      ),
    },
    {
      title: "File Name",
      dataIndex: "file_name",
      key: "file_name",
      width: 200,
      render: (fileName?: string) => (
        <Text code style={{ fontSize: "11px" }}>
          {fileName || "N/A"}
        </Text>
      ),
    },
    {
      title: "Result",
      dataIndex: "validation_result",
      key: "validation_result",
      width: 100,
      render: (result: "VALID" | "INVALID" | "ERROR") => {
        const config = {
          VALID: { color: "success", icon: <CheckCircleOutlined /> },
          INVALID: { color: "warning", icon: <ExclamationCircleOutlined /> },
          ERROR: { color: "error", icon: <ExclamationCircleOutlined /> }
        };
        return (
          <Tag color={config[result].color} icon={config[result].icon}>
            {result}
          </Tag>
        );
      },
    },
    {
      title: "Processing Time",
      dataIndex: "processing_time_ms",
      key: "processing_time_ms",
      width: 120,
      render: (time: number) => (
        <Text>
          <ClockCircleOutlined style={{ marginRight: 4 }} />
          {time}ms
        </Text>
      ),
    },
    {
      title: "Schema",
      dataIndex: "schema_used",
      key: "schema_used",
      width: 180,
      render: (schema?: string) => (
        <Text code style={{ fontSize: "10px" }}>
          {schema?.replace(".json", "") || "N/A"}
        </Text>
      ),
    },
    {
      title: "SNIP Level",
      dataIndex: "snip_level_used",
      key: "snip_level_used",
      width: 100,
      render: (level?: string) => (
        level ? <Tag color="purple">{level}</Tag> : <Text>N/A</Text>
      ),
    },
    {
      title: "Actions",
      key: "actions",
      width: 150,
      render: (_, record: ProcessingLogEntry) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => {
              setSelectedRecord(record);
              setDetailsVisible(true);
            }}
          />
          {record.ta1_generated && (
            <Button
              type="text"
              size="small"
              icon={<DownloadOutlined />}
              title="Download TA1"
            />
          )}
          <Button
            type="text"
            size="small"
            icon={<ReloadOutlined />}
            title="Replay Validation"
          />
        </Space>
      ),
    },
  ];

  const exportProcessingHistory = () => {
    try {
      const csvContent = [
        "Timestamp,Source,File Name,Result,Processing Time (ms),Schema,SNIP Level",
        ...logs.map(log => [
          log.timestamp,
          log.source,
          log.file_name || "",
          log.validation_result,
          log.processing_time_ms,
          log.schema_used || "",
          log.snip_level_used || ""
        ].join(","))
      ].join("\n");

      const blob = new Blob([csvContent], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `processing_history_${new Date().toISOString().split("T")[0]}.csv`;
      
      // Use event approach instead of DOM manipulation for testing compatibility
      if (typeof window !== 'undefined' && document.body) {
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else {
        // Fallback for test environments
        const event = new MouseEvent('click', {
          view: window,
          bubbles: true,
          cancelable: true,
        });
        link.dispatchEvent(event);
      }
      
      URL.revokeObjectURL(url);
    } catch (error) {
      console.warn('Export failed:', error);
    }
  };

  return (
    <div style={{ padding: "24px" }}>
      <Title level={2}>📊 Processing History</Title>
      
      {/* Metrics Dashboard */}
      <Row gutter={[16, 16]} style={{ marginBottom: "24px" }}>
        <Col xs={24} sm={12} md={6}>
          <Card size="small">
            <Statistic
              title="Success Rate"
              value={metrics.success_rate}
              precision={1}
              suffix="%"
              valueStyle={{ color: metrics.success_rate > 90 ? "#3f8600" : "#cf1322" }}
            />
            <Progress percent={metrics.success_rate} showInfo={false} size="small" />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card size="small">
            <Statistic
              title="Avg Processing Time"
              value={metrics.avg_processing_time}
              precision={0}
              suffix="ms"
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card size="small">
            <Statistic
              title="Total Processed"
              value={metrics.total_processed}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card size="small">
            <Statistic
              title="Last 30 Days"
              value={metrics.total_processed}
              suffix="files"
            />
          </Card>
        </Col>
      </Row>

      {/* Quick Stats */}
      <Row gutter={[16, 16]} style={{ marginBottom: "24px" }}>
        <Col xs={24} md={12}>
          <Card title="📈 Common Errors" size="small">
            <Space direction="vertical" style={{ width: "100%" }}>
              {metrics.common_errors.map((error, index) => (
                <div key={index} style={{ display: "flex", justifyContent: "space-between" }}>
                  <Text>{error.error}</Text>
                  <Tag color="red">{error.count}</Tag>
                </div>
              ))}
            </Space>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="📋 Schema Usage" size="small">
            <Space direction="vertical" style={{ width: "100%" }}>
              {metrics.schema_usage.map((schema, index) => (
                <div key={index} style={{ display: "flex", justifyContent: "space-between" }}>
                  <Text code style={{ fontSize: "11px" }}>{schema.schema.replace(".json", "")}</Text>
                  <Tag color="blue">{schema.count}</Tag>
                </div>
              ))}
            </Space>
          </Card>
        </Col>
      </Row>

      {/* Filters and Controls */}
      <Card size="small" style={{ marginBottom: "16px" }}>
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} sm={8} md={4}>
            <Select
              placeholder="Source"
              allowClear
              style={{ width: "100%" }}
              value={selectedFilters.source}
              onChange={(value) => setSelectedFilters(prev => ({ ...prev, source: value }))}
              options={[
                { label: "API", value: "API" },
                { label: "SFTP", value: "SFTP" }
              ]}
            />
          </Col>
          <Col xs={24} sm={8} md={4}>
            <Select
              placeholder="Result"
              allowClear
              style={{ width: "100%" }}
              value={selectedFilters.result}
              onChange={(value) => setSelectedFilters(prev => ({ ...prev, result: value }))}
              options={[
                { label: "Valid", value: "VALID" },
                { label: "Invalid", value: "INVALID" },
                { label: "Error", value: "ERROR" }
              ]}
            />
          </Col>
          <Col xs={24} sm={8} md={8}>
            <RangePicker
              style={{ width: "100%" }}
              onChange={(dates) => {
                if (dates && dates[0] && dates[1]) {
                  setSelectedFilters(prev => ({
                    ...prev,
                    dateRange: [dates[0]!.toISOString(), dates[1]!.toISOString()]
                  }));
                } else {
                  setSelectedFilters(prev => ({ ...prev, dateRange: undefined }));
                }
              }}
            />
          </Col>
          <Col xs={24} sm={24} md={8}>
            <Space>
              <Button
                icon={<ExportOutlined />}
                onClick={exportProcessingHistory}
              >
                Export CSV
              </Button>
              <Button
                onClick={() => setSelectedFilters({})}
              >
                Clear Filters
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* Processing Log Table */}
      <Card title="📋 Processing Log" size="small">
        <Table
          columns={columns}
          dataSource={logs}
          loading={isLoading}
          size="small"
          scroll={{ x: 1200 }}
          pagination={{
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) =>
              `${range[0]}-${range[1]} of ${total} entries`,
          }}
        />
      </Card>

      {/* Details Modal */}
      <Modal
        title="Processing Details"
        open={detailsVisible}
        onCancel={() => setDetailsVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailsVisible(false)}>
            Close
          </Button>
        ]}
        width={600}
      >
        {selectedRecord && (
          <Space direction="vertical" style={{ width: "100%" }}>
            <Alert
              message={`Processing Result: ${selectedRecord.validation_result}`}
              type={selectedRecord.validation_result === "VALID" ? "success" : "error"}
              showIcon
            />
            
            <Descriptions title="Processing Information" column={2} size="small">
              <Descriptions.Item label="Timestamp">
                {new Date(selectedRecord.timestamp).toLocaleString()}
              </Descriptions.Item>
              <Descriptions.Item label="Source">
                <Tag color={selectedRecord.source === "API" ? "blue" : "green"}>
                  {selectedRecord.source}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="File Name">
                <Text code>{selectedRecord.file_name || "N/A"}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Processing Time">
                {selectedRecord.processing_time_ms}ms
              </Descriptions.Item>
              <Descriptions.Item label="Error Count">
                {selectedRecord.error_count}
              </Descriptions.Item>
              <Descriptions.Item label="Schema Used">
                <Text code>{selectedRecord.schema_used || "N/A"}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="SNIP Level">
                {selectedRecord.snip_level_used ? 
                  <Tag color="purple">{selectedRecord.snip_level_used}</Tag> : "N/A"
                }
              </Descriptions.Item>
              <Descriptions.Item label="Profile">
                {selectedRecord.matched_profile || "N/A"}
              </Descriptions.Item>
            </Descriptions>

            <Descriptions title="Generated Responses" column={2} size="small">
              <Descriptions.Item label="TA1 Generated">
                <Tag color={selectedRecord.ta1_generated ? "success" : "default"}>
                  {selectedRecord.ta1_generated ? "Yes" : "No"}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="999 Generated">
                <Tag color={selectedRecord.ta1_999_generated ? "success" : "default"}>
                  {selectedRecord.ta1_999_generated ? "Yes" : "No"}
                </Tag>
              </Descriptions.Item>
            </Descriptions>

            {(selectedRecord.ta1_generated || selectedRecord.ta1_999_generated) && (
              <Space>
                {selectedRecord.ta1_generated && (
                  <Button icon={<DownloadOutlined />}>
                    Download TA1
                  </Button>
                )}
                {selectedRecord.ta1_999_generated && (
                  <Button icon={<DownloadOutlined />}>
                    Download 999
                  </Button>
                )}
              </Space>
            )}
          </Space>
        )}
      </Modal>
    </div>
  );
};