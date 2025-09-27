import React from 'react';
import { Card, Typography } from 'antd';

const { Title } = Typography;

interface DarkPageContainerProps {
  children: React.ReactNode;
  title?: string;
  description?: string;
  extra?: React.ReactNode;
}

export const DarkPageContainer: React.FC<DarkPageContainerProps> = ({
  children,
  title,
  description,
  extra
}) => {
  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%)',
        padding: '24px',
      }}
    >
      <div style={{ maxWidth: '1600px', margin: '0 auto' }}>
        {(title || description || extra) && (
          <div style={{ marginBottom: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                {title && (
                  <Title level={2} style={{ color: 'white', marginBottom: description ? '8px' : '0' }}>
                    {title}
                  </Title>
                )}
                {description && (
                  <Typography.Paragraph style={{ color: 'rgba(255, 255, 255, 0.65)', marginBottom: 0 }}>
                    {description}
                  </Typography.Paragraph>
                )}
              </div>
              {extra && <div>{extra}</div>}
            </div>
          </div>
        )}
        
        <Card
          style={{
            borderRadius: '8px',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.3)',
            border: 'none',
          }}
          bodyStyle={{ padding: 0 }}
        >
          {children}
        </Card>
      </div>
    </div>
  );
};