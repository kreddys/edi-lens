export interface FlowDefinition {
  name: string;
  description: string;
  processors: any[];
  connections: any[];
  process_groups: any[];
  parameters?: Record<string, any>;
}

export interface Template {
  id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  definition?: FlowDefinition;
  parameters: Record<string, any>;
  processor_count: number;
  connection_count: number;
  parameter_count: number;
  usage_count: number;
  created_at?: string;
  updated_at?: string;
}