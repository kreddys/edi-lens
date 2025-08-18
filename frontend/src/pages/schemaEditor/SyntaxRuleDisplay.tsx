import React from "react";
import { Typography, Card, Space, Tag } from "antd";

const { Text } = Typography;

interface RuleClauseProps {
    clause: {
        element?: string;
        elements?: string[];
        operator?: string;
        assertion?: string;
        value?: any;
    };
    type: 'condition' | 'assertion';
}

const RuleClause: React.FC<RuleClauseProps> = ({ clause, type }) => {
    const renderElement = (el: string) => <Tag color="blue">{el}</Tag>;
    const renderOperator = (op: string) => <Text strong style={{ margin: '0 4px' }}>{op.replace(/_/g, ' ')}</Text>;
    const renderValue = (val: any) => <Tag color="purple">{String(val)}</Tag>;

    if (type === 'condition') {
        if (clause.elements) {
            return (
                <Space size="small">
                    {renderOperator(clause.operator!)}
                    {clause.elements.map(el => renderElement(el))}
                </Space>
            );
        }
        return (
            <Space size="small">
                {renderElement(clause.element!)}
                {renderOperator(clause.operator!)}
                {clause.value && renderValue(clause.value)}
            </Space>
        );
    }

    if (type === 'assertion') {
        if (clause.elements) {
            return (
                <Space size="small">
                    {renderOperator(clause.assertion!)}
                    {clause.elements.map(el => renderElement(el))}
                </Space>
            );
        }
        return (
            <Space size="small">
                {renderElement(clause.element!)}
                {renderOperator(clause.assertion!)}
                {clause.value && renderValue(clause.value)}
            </Space>
        );
    }
    return null;
};

export const SyntaxRuleDisplay: React.FC<{ rule: any }> = ({ rule }) => {
    const conditions = rule.conditions?.ALL_OF || rule.conditions?.ANY_OF || [];
    const logicalOperator = rule.conditions?.ALL_OF ? "AND" : "OR";

    return (
        <Card size="small" title={<Text>Rule: <Text code>{rule.ruleId}</Text></Text>} style={{ marginBottom: 12 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
                <Text type="secondary">{rule.description}</Text>
                
                {conditions.length > 0 && (
                    <Card type="inner" size="small" title={<Space><Text strong>IF</Text><Tag>{logicalOperator}</Tag></Space>}>
                        <Space direction="vertical" align="start">
                            {conditions.map((cond: any, index: number) => (
                                <RuleClause key={index} clause={cond} type="condition" />
                            ))}
                        </Space>
                    </Card>
                )}

                <Card type="inner" size="small" title={<Text strong>THEN</Text>}>
                     <Space direction="vertical" align="start">
                        {rule.then.map((assertion: any, index: number) => (
                            <RuleClause key={index} clause={assertion} type="assertion" />
                        ))}
                    </Space>
                </Card>
            </Space>
        </Card>
    );
};