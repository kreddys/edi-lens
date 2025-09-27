import React, { useState } from 'react';
import { Card, Button } from 'antd';
import { UpOutlined, DownOutlined } from '@ant-design/icons';

interface MinimizableCardProps {
  title: React.ReactNode;
  children: React.ReactNode;
  defaultMinimized?: boolean;
  size?: 'default' | 'small';
  style?: React.CSSProperties;
  bodyStyle?: React.CSSProperties;
}

export const MinimizableCard: React.FC<MinimizableCardProps> = ({
  title,
  children,
  defaultMinimized = false,
  size = 'small',
  style,
  bodyStyle
}) => {
  const [minimized, setMinimized] = useState(defaultMinimized);

  const toggleMinimized = () => {
    setMinimized(!minimized);
  };

  return (
    <Card
      title={
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>{title}</div>
          <Button
            type="text"
            size="small"
            icon={minimized ? <DownOutlined /> : <UpOutlined />}
            onClick={toggleMinimized}
            style={{ marginLeft: '8px' }}
          />
        </div>
      }
      size={size}
      style={{ 
        marginBottom: '16px',
        ...style
      }}
      bodyStyle={minimized ? { display: 'none' } : bodyStyle}
    >
      {children}
    </Card>
  );
};