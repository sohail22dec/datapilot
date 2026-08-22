export type MessageRole = "user" | "assistant";

export interface QueryDataRow {
  [key: string]: string | number | boolean | null | undefined;
}

export type ChartType = "bar" | "line" | "area" | "donut";

export interface ChartConfig {
  type: ChartType | null;
  x_key?: string;
  y_key?: string;
  title?: string;
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  sql?: string;
  data?: QueryDataRow[];
  columns?: string[];
  rowCount?: number;
  executionTimeMs?: number;
  chartConfig?: ChartConfig | null;
  isStreaming?: boolean;
  steps?: string[];
  thoughtTrace?: string[];
}

export interface Conversation {
  id: string;
  title: string;
  timestamp: string;
  messages: Message[];
}

export interface UserProfile {
  name: string;
  avatarUrl?: string;
}
