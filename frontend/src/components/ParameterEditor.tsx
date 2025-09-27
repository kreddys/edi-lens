import React from 'react';
import { Input, Space, Typography, Button } from 'antd';
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface ParameterEditorProps {
  parameters: Record<string, string>;
  onParametersChange: (parameters: Record<string, string>) => void;
  templateParameters?: Record<string, { description: string; default: string }>;
  disabled?: boolean;
}

export const ParameterEditor: React.FC<ParameterEditorProps> = ({
  parameters,
  onParametersChange,
  templateParameters = {},
  disabled = false
}) => {
  const handleParameterChange = (name: string, value: string) => {
    const newParameters = { ...parameters, [name]: value };
    onParametersChange(newParameters);
  };

  const addParameter = () => {
    const newKey = `param_${Date.now()}`;
    const newParameters = { ...parameters, [newKey]: '' };
    onParametersChange(newParameters);
  };

  const removeParameter = (name: string) => {
    const newParameters = { ...parameters };
    delete newParameters[name];
    onParametersChange(newParameters);
  };

  const handleParameterNameChange = (oldName: string, newName: string) => {
    if (oldName === newName) return;
    
    const newParameters = { ...parameters };
    const value = newParameters[oldName];
    delete newParameters[oldName];
    newParameters[newName] = value;
    onParametersChange(newParameters);
  };

  // Get template parameters that are not yet in the current parameters
  const templateParamNames = Object.keys(templateParameters);
  const missingTemplateParams = templateParamNames.filter(name => !(name in parameters));

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      {/* Template parameters */}
      {templateParamNames.map(paramName => (
        <div key={paramName} style={{ marginBottom: '8px' }}>
          <Text strong style={{ fontSize: '12px', color: '#1890ff', display: 'block', marginBottom: '4px' }}>
            {paramName}
          </Text>
          <Input
            value={parameters[paramName] || templateParameters[paramName]?.default || ''}
            onChange={(e) => handleParameterChange(paramName, e.target.value)}
            placeholder={templateParameters[paramName]?.default || 'Enter value'}
            disabled={disabled}
            size="small"
          />
          {templateParameters[paramName]?.description && (
            <Text type="secondary" style={{ fontSize: '11px', display: 'block', marginTop: '2px' }}>
              {templateParameters[paramName].description}
            </Text>
          )}
        </div>
      ))}

      {/* Custom parameters */}
      {Object.entries(parameters)
        .filter(([name]) => !templateParamNames.includes(name))
        .map(([name, value]) => (
          <div key={name} style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '8px' }}>
            <Input
              value={name}
              onChange={(e) => handleParameterNameChange(name, e.target.value)}
              placeholder="Parameter name"
              disabled={disabled}
              style={{ width: '120px' }}
              size="small"
            />
            <Input
              value={value}
              onChange={(e) => handleParameterChange(name, e.target.value)}
              placeholder="Parameter value"
              disabled={disabled}
              style={{ flex: 1 }}
              size="small"
            />
            <Button
              type="text"
              icon={<MinusCircleOutlined />}
              onClick={() => removeParameter(name)}
              disabled={disabled}
              size="small"
              danger
            />
          </div>
        ))}

      {/* Add parameter button */}
      <Button
        type="dashed"
        icon={<PlusOutlined />}
        onClick={addParameter}
        disabled={disabled}
        size="small"
        style={{ width: '100%' }}
      >
        Add Custom Parameter
      </Button>

      {/* Add missing template parameters button */}
      {missingTemplateParams.length > 0 && (
        <div style={{ marginTop: '8px' }}>
          <Text type="secondary" style={{ fontSize: '11px', display: 'block', marginBottom: '4px' }}>
            Missing template parameters:
          </Text>
          <div>
            {missingTemplateParams.map(paramName => (
              <Button
                key={paramName}
                type="dashed"
                size="small"
                onClick={() => handleParameterChange(paramName, templateParameters[paramName]?.default || '')}
                style={{ marginRight: '4px', marginBottom: '4px' }}
              >
                + {paramName}
              </Button>
            ))}
          </div>
        </div>
      )}

      {Object.keys(parameters).length === 0 && templateParamNames.length === 0 && (
        <Text type="secondary" style={{ fontSize: '12px', textAlign: 'center', display: 'block' }}>
          No parameters defined. Template parameters will be loaded automatically.
        </Text>
      )}
    </Space>
  );
};