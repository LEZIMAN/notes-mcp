/** 笔记标题项 */
export interface TopicItem {
  title: string;
  source: string;
}

/** 知识库统计 */
export interface Stats {
  total_files: number;
  total_chunks: number;
  embed_model: string;
  notes_dirs: string[];
}

/** 搜索命中 */
export interface SearchHit {
  title: string;
  snippet: string;
  source: string;
  score: number;
}

/** 聊天消息 */
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

/** 学习模式类型 */
export type LearningMode = 'explain' | 'review' | 'quiz' | 'compare';

/** API 响应 */
export interface ApiChatResponse {
  reply: string;
}

export interface ApiNoteResponse {
  title: string;
  content: string;
}

export interface ApiSearchResponse {
  query: string;
  result: string;
}
