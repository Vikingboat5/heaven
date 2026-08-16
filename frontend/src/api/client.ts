/** API 客户端: 鉴权请求 + SSE 流式对话 */

export interface UserOut {
  id: number
  username: string
}
export interface TokenOut {
  token: string
  user: UserOut
}
export interface EggOut {
  id: number
  rarity: string
  hatch_value: number
  hatch_target: number
  care_remaining: number
  quiz_done: boolean
}
export interface QuizOption {
  key: string
  text: string
}
export interface QuizQuestion {
  key: string
  text: string
  type: 'choice' | 'choice_or_text' | 'text'
  optional: boolean
  max_len: number | null
  options: QuizOption[]
}
export interface TalentOut {
  id: string
  name: string
  desc: string
}
export interface SkillOut {
  id: string
  name: string
  category: string
  desc: string
}
export interface PetOut {
  id: number
  name: string
  species: string
  color: string
  rarity: string
  personality: { tags: string[]; [key: string]: unknown }
  talents: TalentOut[]
  skills: SkillOut[]
  level: number
  exp: number
  inventory: { item: string; count: number }[]
  sprite_status: string
  sprite_style: string
}
export interface AdventureLogOut {
  id: number
  title?: string | null
  narrative: string
  rewards: { exp?: number; items?: string[] }
  started_at: string | null
  ended_at: string | null
  events?: { time: string; text: string }[]
}
export interface ChatHistoryOut {
  messages: { role: 'user' | 'pet'; content: string }[]
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

export function getToken(): string {
  return localStorage.getItem('pp_token') ?? ''
}

function handleUnauthorized(): void {
  localStorage.removeItem('pp_token')
  localStorage.removeItem('pp_username')
  if (location.pathname !== '/login') {
    location.href = '/login'
  }
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const resp = await fetch(path, { ...options, headers })
  if (resp.status === 401) {
    handleUnauthorized()
    throw new ApiError(401, '登录已过期')
  }
  const data = await resp.json().catch(() => null)
  if (!resp.ok) {
    throw new ApiError(resp.status, (data as { detail?: string })?.detail ?? `请求失败: ${resp.status}`)
  }
  return data as T
}

export const api = {
  register: (username: string, password: string) =>
    request<TokenOut>('/api/auth/register', { method: 'POST', body: JSON.stringify({ username, password }) }),
  login: (username: string, password: string) =>
    request<TokenOut>('/api/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  getCurrentEgg: () => request<EggOut | null>('/api/eggs/current'),
  careEgg: () => request<EggOut>('/api/eggs/care', { method: 'POST' }),
  hatchEgg: (name?: string) =>
    request<PetOut>('/api/eggs/hatch', { method: 'POST', body: JSON.stringify({ name: name || null }) }),
  getMyPet: () => request<PetOut | null>('/api/pets/me'),
  getQuiz: () => request<QuizQuestion[]>('/api/quiz'),
  submitQuiz: (answers: Record<string, string>) =>
    request<EggOut>('/api/eggs/quiz', { method: 'POST', body: JSON.stringify({ answers }) }),
  checkAdventure: () => request<{ new_log: AdventureLogOut | null }>('/api/adventure/check'),
  getAdventureLogs: (limit = 20) => request<{ logs: AdventureLogOut[] }>(`/api/adventure/logs?limit=${limit}`),
  getChatHistory: () => request<ChatHistoryOut>('/api/dialogue/history'),
}

/** 流式对话: 逐段回调 content delta; 历史由服务端按宠物持久化, 前端只传当前消息 */
export async function streamChat(
  message: string,
  onDelta: (text: string) => void,
  onError?: (message: string) => void,
): Promise<void> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const resp = await fetch('/api/dialogue/chat', {
    method: 'POST',
    headers,
    body: JSON.stringify({ message }),
  })
  if (resp.status === 401) {
    handleUnauthorized()
    onError?.('登录已过期')
    return
  }
  if (!resp.ok || !resp.body) {
    const data = await resp.json().catch(() => null)
    onError?.((data as { detail?: string })?.detail ?? `请求失败: ${resp.status}`)
    return
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // 按 SSE 事件分割 (data: ...\n\n)
    const events = buffer.split('\n\n')
    buffer = events.pop() ?? ''
    for (const evt of events) {
      const line = evt.trim()
      if (!line.startsWith('data:')) continue
      const payload = line.slice(5).trim()
      if (payload === '[DONE]') return
      try {
        const data = JSON.parse(payload)
        if (data.delta) onDelta(data.delta)
        if (data.error) onError?.(data.detail ?? data.error)
      } catch {
        // 忽略不完整分片
      }
    }
  }
}
