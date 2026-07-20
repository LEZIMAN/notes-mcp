import type {
  ApiChatResponse,
  ApiNoteResponse,
  ApiSearchResponse,
  Stats,
} from '../types';

const BASE = '/api';

async function request<T>(url: string): Promise<T> {
  const res = await fetch(`${BASE}${url}`);
  if (!res.ok) {
    throw new Error(`API 请求失败: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

/** POST /api/chat — 智能对话,支持 sessionId */
export async function sendMessage(
  message: string,
  sessionId?: string,
): Promise<{ reply: string; sessionId: string }> {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, sessionId: sessionId || '' }),
  });
  if (!res.ok) {
    throw new Error(`对话请求失败: ${res.status}`);
  }
  return res.json();
}

// ===== 会话管理 =====

export interface SessionInfo {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  preview: string
}

export interface SessionMessages {
  sessionId: string
  messages: { role: string; content: string; createdAt: number }[]
}

/** GET /api/sessions */
export async function fetchSessions(): Promise<{ sessions: SessionInfo[] }> {
  const res = await fetch(`${BASE}/sessions`);
  return res.json();
}

/** POST /api/sessions */
export async function createSession(): Promise<SessionInfo> {
  const res = await fetch(`${BASE}/sessions`, { method: 'POST' });
  return res.json();
}

/** GET /api/sessions/{id} */
export async function fetchSessionMessages(id: string): Promise<SessionMessages> {
  const res = await fetch(`${BASE}/sessions/${id}`);
  return res.json();
}

/** DELETE /api/sessions/{id} */
export async function deleteSessionApi(id: string): Promise<void> {
  await fetch(`${BASE}/sessions/${id}`, { method: 'DELETE' });
}

/** GET /api/stats — 知识库统计 */
export async function fetchStats(): Promise<Stats> {
  return request<Stats>('/stats');
}

/** GET /api/topics — 笔记标题列表 */
export async function fetchTopics(): Promise<string> {
  const res = await fetch(`${BASE}/topics`);
  return res.text();
}

/** GET /api/notes/{title} — 取笔记原文 */
export async function fetchNote(title: string): Promise<ApiNoteResponse> {
  return request<ApiNoteResponse>(`/notes/${encodeURIComponent(title)}`);
}

/** GET /api/search — 搜索笔记 */
export async function searchNotes(
  query: string,
  topK = 5,
): Promise<ApiSearchResponse> {
  return request<ApiSearchResponse>(
    `/search?q=${encodeURIComponent(query)}&top_k=${topK}`,
  );
}
