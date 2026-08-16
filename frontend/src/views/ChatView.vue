<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { api, streamChat } from '../api/client'

interface Message {
  role: 'user' | 'pet'
  content: string
}

const messages = ref<Message[]>([])
const input = ref('')
const sending = ref(false)
const listEl = ref<HTMLElement>()

const petName = ref('')
const petTags = ref<string[]>([])
const hasPet = ref(true) // false 时提示先去孵化
const loading = ref(true)

onMounted(async () => {
  try {
    const p = await api.getMyPet()
    if (p) {
      petName.value = p.name
      petTags.value = p.personality.tags ?? []
      // 对话历史服务端持久化: 挂载时回显, 切换页面回来不丢
      const hist = await api.getChatHistory()
      messages.value = hist.messages.map((m) => ({ role: m.role, content: m.content }))
      await scrollToBottom()
    } else {
      hasPet.value = false
    }
  } catch (err) {
    // 历史加载失败不阻塞对话, 视为空历史 — 但必须留痕, 否则排查时无迹可寻
    console.error('加载对话历史失败:', err)
  } finally {
    loading.value = false
  }
})

async function scrollToBottom() {
  await nextTick()
  listEl.value?.scrollTo({ top: listEl.value.scrollHeight })
}

async function send() {
  const text = input.value.trim()
  if (!text || sending.value || !hasPet.value) return
  input.value = ''
  sending.value = true

  messages.value.push({ role: 'user', content: text })
  const petMsg = { role: 'pet' as const, content: '' }
  messages.value.push(petMsg)
  await scrollToBottom()

  // 对话历史由服务端按宠物持久化, 前端只发送当前消息
  await streamChat(
    text,
    (delta) => {
      petMsg.content += delta
      scrollToBottom()
    },
    (err) => {
      petMsg.content = `(出错了: ${err})`
    },
  )
  sending.value = false
}
</script>

<template>
  <div class="chat">
    <!-- 背景 -->
    <div class="chat-bg"></div>
    <span class="bg-star bs1"></span>
    <span class="bg-star bs2"></span>
    <span class="bg-star bs3"></span>
    <span class="bg-star bs4"></span>

    <div ref="listEl" class="message-list">
      <!-- 加载中 -->
      <div v-if="loading" class="empty">
        <p class="empty-hint">加载中…</p>
      </div>

      <!-- 还没有宠物 -->
      <div v-else-if="!hasPet" class="empty">
        <p class="empty-title">你还没有宠物</p>
        <p class="empty-hint">先回家园把宠物蛋孵化出来吧</p>
        <router-link to="/" class="home-link">回家园 →</router-link>
      </div>

      <!-- 空对话状态 -->
      <div v-else-if="messages.length === 0" class="empty">
        <div class="empty-egg">
          <svg viewBox="0 0 48 62" width="54" height="70">
            <defs>
              <linearGradient id="empty-egg-body" x1="0" y1="0" x2="0.4" y2="1">
                <stop offset="0%" stop-color="#fff9ec" />
                <stop offset="100%" stop-color="#f0cda0" />
              </linearGradient>
            </defs>
            <path
              d="M24,2 C36,2 46,22 46,38 C46,52 36,60 24,60 C12,60 2,52 2,38 C2,22 12,2 24,2 Z"
              fill="url(#empty-egg-body)"
            />
            <path
              d="M9,32 Q16.5,26.5 24,32 T39,32"
              stroke="#b48ac7"
              stroke-width="3"
              stroke-linecap="round"
              fill="none"
              opacity="0.85"
            />
            <circle cx="15" cy="42" r="2.4" fill="#b48ac7" opacity="0.85" />
            <circle cx="31" cy="44" r="2.4" fill="#b48ac7" opacity="0.85" />
            <ellipse cx="16" cy="16" rx="4.5" ry="9" fill="#fff" opacity="0.6" transform="rotate(-16 16 16)" />
          </svg>
        </div>
        <p class="empty-title">「{{ petName }}」正在等你</p>
        <p class="empty-hint">和它打个招呼吧 · {{ petTags.join(' · ') }}</p>
      </div>

      <div
        v-for="(m, i) in messages"
        :key="i"
        class="msg-row"
        :class="m.role === 'user' ? 'me' : 'pet'"
      >
        <span v-if="m.role === 'pet'" class="avatar">
          <svg viewBox="0 0 48 62" width="24" height="31">
            <path
              d="M24,2 C36,2 46,22 46,38 C46,52 36,60 24,60 C12,60 2,52 2,38 C2,22 12,2 24,2 Z"
              fill="#f5ddb8"
            />
            <path
              d="M9,32 Q16.5,26.5 24,32 T39,32"
              stroke="#b48ac7"
              stroke-width="3"
              stroke-linecap="round"
              fill="none"
              opacity="0.85"
            />
          </svg>
        </span>
        <div class="bubble" :class="m.role === 'user' ? 'me' : 'pet'">
          <!-- 等待首个字: 思考动画 -->
          <span
            v-if="m.role === 'pet' && !m.content && sending && i === messages.length - 1"
            class="thinking"
          >
            <span class="thinking-label">{{ petName }}思考中</span>
            <span class="dot"></span><span class="dot"></span><span class="dot"></span>
          </span>
          <template v-else>
            {{ m.content
            }}<span v-if="m.role === 'pet' && sending && i === messages.length - 1" class="cursor"
              >▍</span
            >
          </template>
        </div>
      </div>
    </div>
    <form class="input-bar" @submit.prevent="send">
      <input v-model="input" :placeholder="`和${petName || '宠物'}说点什么…`" :disabled="sending || !hasPet" />
      <button type="submit" :disabled="sending || !input.trim() || !hasPet">发送</button>
    </form>
  </div>
</template>

<style scoped>
.chat {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

/* 背景：深夜紫渐变 */
.chat-bg {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, #1b1040 0%, #2c1a4e 55%, #3d2358 100%);
}
.bg-star {
  position: absolute;
  width: 2px;
  height: 2px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 0 6px 1px rgba(255, 255, 255, 0.7);
  animation: twinkle 3s ease-in-out infinite;
  pointer-events: none;
}
.bs1 { top: 70px; left: 40px; }
.bs2 { top: 150px; right: 56px; animation-delay: 0.8s; }
.bs3 { top: 42%; left: 26px; animation-delay: 1.6s; }
.bs4 { top: 60%; right: 30px; animation-delay: 2.3s; }
@keyframes twinkle {
  0%, 100% { opacity: 0.2; }
  50% { opacity: 0.9; }
}

.message-list {
  position: relative;
  z-index: 1;
  flex: 1;
  overflow-y: auto;
  padding: 18px 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* 空状态 */
.empty {
  text-align: center;
  margin-top: 72px;
}
.empty-egg {
  display: inline-block;
  animation: bob 3s ease-in-out infinite;
  filter: drop-shadow(0 8px 20px rgba(240, 205, 160, 0.3));
}
@keyframes bob {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-9px); }
}
.empty-title {
  margin: 16px 0 6px;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 2px;
  color: var(--color-text);
}
.empty-hint {
  margin: 0;
  font-size: 12px;
  letter-spacing: 1px;
  color: var(--color-text-faint);
}
.home-link {
  display: inline-block;
  margin-top: 18px;
  padding: 10px 22px;
  border-radius: 999px;
  background: linear-gradient(135deg, #f2a56e, #e77fa2);
  color: #fff;
  font-size: 14px;
  text-decoration: none;
  letter-spacing: 1px;
}

/* 消息行 */
.msg-row {
  display: flex;
  align-items: flex-end;
  gap: 9px;
}
.msg-row.me {
  justify-content: flex-end;
}
.avatar {
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.14);
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 气泡 */
.bubble {
  max-width: 75%;
  padding: 11px 15px;
  white-space: pre-wrap;
  line-height: 1.65;
  font-size: 15px;
}
.bubble.pet {
  background: rgba(255, 255, 255, 0.09);
  border: 1px solid rgba(255, 255, 255, 0.13);
  border-radius: 4px 18px 18px 18px;
  color: var(--color-text);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
.bubble.me {
  background: linear-gradient(135deg, #f2a56e, #e77fa2);
  border-radius: 18px 4px 18px 18px;
  color: #fff;
  box-shadow: 0 4px 14px rgba(231, 127, 162, 0.3);
}
.cursor {
  animation: blink 0.9s step-end infinite;
  color: #f2a56e;
}
@keyframes blink {
  50% { opacity: 0; }
}

/* 思考动画 */
.thinking {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.thinking-label {
  font-size: 13px;
  color: var(--color-text-dim);
  margin-right: 5px;
  letter-spacing: 1px;
}
.dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #f2a56e;
  animation: dot-bounce 1.2s ease-in-out infinite;
}
.dot:nth-child(3) { animation-delay: 0.15s; }
.dot:nth-child(4) { animation-delay: 0.3s; }
@keyframes dot-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}

/* 输入栏 */
.input-bar {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  background: rgba(21, 12, 46, 0.6);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}
.input-bar input {
  flex: 1;
  padding: 11px 18px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 999px;
  outline: none;
  font-size: 15px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--color-text);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.input-bar input:focus {
  border-color: rgba(242, 165, 110, 0.55);
  box-shadow: 0 0 0 4px rgba(242, 165, 110, 0.12);
}
.input-bar input::placeholder {
  color: rgba(253, 240, 220, 0.35);
}
.input-bar button {
  padding: 11px 22px;
  border: none;
  border-radius: 999px;
  background: linear-gradient(135deg, #f2a56e, #e77fa2);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 1px;
  box-shadow: 0 4px 14px rgba(231, 127, 162, 0.35);
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}
.input-bar button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(231, 127, 162, 0.5);
}
.input-bar button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
