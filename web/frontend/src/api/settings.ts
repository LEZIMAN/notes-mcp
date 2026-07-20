const BASE = '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, options);
  if (!res.ok) {
    throw new Error(`API 请求失败: ${res.status}`);
  }
  return res.json();
}

export interface ProviderConfig {
  name: string;
  baseUrl: string;
  apiKey: string;
  selectedModel: string;
  hasKey: boolean;
}

export type ProviderType = 'ollama' | 'openai' | 'custom';

export interface Settings {
  notesDir: string;
  activeProvider: ProviderType;
  ollama: ProviderConfig;
  openai: ProviderConfig;
  custom: ProviderConfig;
}

export interface ModelsResponse {
  provider: ProviderType;
  current: string;
  models: { name: string; size?: string; ownedBy?: string }[];
}

/** GET /api/settings */
export async function fetchSettings(): Promise<Settings> {
  return request<Settings>('/settings');
}

/** PUT /api/settings — 更新 provider 配置 */
export async function updateProvider(
  provider: ProviderType,
  config: Partial<ProviderConfig>,
) {
  return request('/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider, ...config }),
  });
}

/** PUT /api/settings — 更新笔记目录 */
export async function updateNotesDir(notesDir: string) {
  return request<{ message: string; notesDir: string; requiresRestart: boolean }>(
    '/settings',
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notesDir }),
    },
  );
}

/** POST /api/provider/select */
export async function selectProvider(provider: ProviderType) {
  return request('/provider/select', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider }),
  });
}

/** GET /api/models */
export async function fetchModels(): Promise<ModelsResponse> {
  return request<ModelsResponse>('/models');
}

/** POST /api/models/select */
export async function selectModel(model: string) {
  return request('/models/select', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model }),
  });
}

/** POST /api/models/refresh */
export async function refreshModels(): Promise<ModelsResponse> {
  return request<ModelsResponse>('/models/refresh', { method: 'POST' });
}
