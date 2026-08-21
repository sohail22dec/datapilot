export type MessageRole = "user" | "assistant";

export interface QueryDataRow {
  [key: string]: string | number | boolean | null | undefined;
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
