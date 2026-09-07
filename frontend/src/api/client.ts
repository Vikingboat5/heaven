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
/** 背包物品 (v1.2: 富化, join 物品定义) */
export interface InventoryItemOut {
  item_id: string
  name: string
  rarity: 'common' | 'rare' | 'epic'
  attr: 'food' | 'gift' | 'charm' | 'antique'
  image: string
  count: number
  is_new: boolean
  acquired_at: string
  acquired_zone: string
  acquired_via: string
}
/** 行囊 (三槽位, 值为 item_id 或 null) */
export interface LoadoutOut {
  food?: string | null
  gift?: string | null
  charm?: string | null
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
  inventory: InventoryItemOut[]
  loadout: LoadoutOut
  sprite_status: string
  sprite_style: string
  away: boolean
  travel: Record<string, string>
}
/** 收获物品 (日志/信件里的富化结构; 同物品已按 count 合并) */
export interface RewardItemOut {
  item_id: string
  name: string
  rarity: 'common' | 'rare' | 'epic'
  attr: string
  image: string
  is_new: boolean
  count: number
}
export interface AdventureLogOut {
  id: number
  title?: string | null
  narrative: string
  rewards: {
    exp?: number
    items?: RewardItemOut[]
    consumed?: string[]
    exchanged?: { gave: string; got: string; with: string } | null
    gift_returned?: boolean
    postcard?: string | null
    postcard_pending?: boolean
  }
  dest?: string
  flavor?: string
  started_at: string | null
  ended_at: string | null
  events?: { time: string; type?: string; text: string }[]
}
/** 图鉴目录物品 */
export interface CatalogItemOut {
  item_id: string
  name: string
  desc: string
  rarity: 'common' | 'rare' | 'epic'
  attr: 'food' | 'gift' | 'charm' | 'antique'
  image: string
  pack: string
  seed_name: string
  obtained: boolean
  count: number
  is_new: boolean
  first_discovery: { by_username: string; at: string | null } | null
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
  // H7: 宠物详情页操作
  renamePet: (name: string) =>
    request<{ ok: boolean; name: string }>('/api/pets/rename', { method: 'POST', body: JSON.stringify({ name }) }),
  regenSprite: () => request<{ ok: boolean; detail?: string }>('/api/pets/regen_sprite', { method: 'POST' }),
  getQuiz: () => request<QuizQuestion[]>('/api/quiz'),
  submitQuiz: (answers: Record<string, string>) =>
    request<EggOut>('/api/eggs/quiz', { method: 'POST', body: JSON.stringify({ answers }) }),
  checkAdventure: () =>
    request<{ event: string; log: AdventureLogOut | null; back_at: string | null; dest?: string }>('/api/adventure/check'),
  leaveAdventure: (loadout?: LoadoutOut) =>
    request<{ ok: boolean; back_at?: string; dest?: string; detail?: string }>('/api/adventure/leave', {
      method: 'POST',
      body: JSON.stringify(loadout ?? {}),
    }),
  getLoadout: () => request<LoadoutOut>('/api/adventure/loadout'),
  getAdventureLogs: (limit = 20) => request<{ logs: AdventureLogOut[] }>(`/api/adventure/logs?limit=${limit}`),
  getCatalog: () => request<{ items: CatalogItemOut[] }>('/api/items/catalog'),
  markItemsSeen: (itemIds: string[]) =>
    request<{ cleared: number }>('/api/items/mark_seen', { method: 'POST', body: JSON.stringify({ item_ids: itemIds }) }),
  getChatHistory: () => request<ChatHistoryOut>('/api/dialogue/history'),
}

/** 品级/属性中文与配色 (图鉴/信件共用) */
export const RARITY_LABELS: Record<string, string> = { common: '常见', rare: '稀有', epic: '传说' }
export const ATTR_LABELS: Record<string, string> = { food: '口粮', gift: '伴手礼', charm: '护身符', antique: '古董' }
export const PACK_LABELS: Record<string, string> = {
  myth_shanhaijing_east: '山海经·东',
  field_common: '通用野区',
  misc: '其他',
}
/** 物品图 URL (与 PetSprite 一致走 /static 相对路径, dev 由 vite 代理到后端) */
export function itemImageUrl(image: string): string {
  return image || ''
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
