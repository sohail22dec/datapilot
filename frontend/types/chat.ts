export type MessageRole = "user" | "assistant";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
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
