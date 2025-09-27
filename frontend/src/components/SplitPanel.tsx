import React from 'react';
import { Row, Col } from 'antd';

interface SplitPanelProps {
  leftPanel: React.ReactNode;
  rightPanel: React.ReactNode;
  leftSpan?: number;
  rightSpan?: number;
  gutter?: number;
  style?: React.CSSProperties;
}

export const SplitPanel: React.FC<SplitPanelProps> = ({
  leftPanel,
  rightPanel,
  leftSpan = 12,
  rightSpan = 12,
  gutter = 16,
  style = {}
}) => {
  return (
    <div style={{ padding: '24px', ...style }}>
      <Row gutter={gutter} style={{ minHeight: '70vh' }}>
        <Col span={leftSpan}>
          <div style={{ height: '100%' }}>
            {leftPanel}
          </div>
        </Col>
        <Col span={rightSpan}>
          <div style={{ height: '100%' }}>
            {rightPanel}
          </div>
        </Col>
      </Row>
    </div>
  );
};