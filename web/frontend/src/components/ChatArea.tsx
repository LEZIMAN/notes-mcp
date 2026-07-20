import { useState, useRef, useEffect } from 'react'
import { message } from 'antd'
import { UserOutlined, RobotOutlined } from '@ant-design/icons'
import { sendMessage, fetchSessionMessages } from '../api/client'
import type { ChatMessage } from '../types'
import WelcomeState from './WelcomeState'
import ChatInput from './ChatInput'
import SourceCitation from './SourceCitation'
import MarkdownRenderer from './MarkdownRenderer'

interface Props {
  sessionId: string
  onSessionCreated: (id: string) => void
  refreshSessions: () => void
}

/** 快捷指令 prompt 前缀 */
function makePrompt(action: string): string {
  return ({
    explain: '请帮我讲解一个概念：',
    review: '请帮我生成复习材料，主题：',
    quiz: '请基于笔记给我出 5 道自测题，主题：',
    compare: '请对比分析以下两个概念：',
  } as Record<string, string>)[action] || ''
}

export default function ChatArea({ sessionId, onSessionCreated, refreshSessions }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [activeAction, setActiveAction] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const [hasWelcome, setHasWelcome] = useState(true)

  // 加载历史消息
  useEffect(() => {
    if (!sessionId) {
      setMessages([])
      setHasWelcome(true)
      return
    }
    fetchSessionMessages(sessionId)
      .then((d) => {
        const msgs: ChatMessage[] = d.messages.map((m, i) => ({
          id: `hist-${i}`,
          role: m.role as 'user' | 'assistant',
          content: m.content,
          timestamp: m.createdAt,
        }))
        setMessages(msgs)
        setHasWelcome(msgs.length === 0)
      })
      .catch(() => setHasWelcome(true))
  }, [sessionId])

  // 滚动到底
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (text: string) => {
    const finalText =
      activeAction && !text.startsWith('请')
        ? `${makePrompt(activeAction)}${text}`
        : text

    if (activeAction) setActiveAction('')

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: Date.now(),
    }
    setMessages((prev) => [...prev, userMsg])
    setHasWelcome(false)
    setLoading(true)

    try {
      const res = await sendMessage(finalText, sessionId || undefined)
      // 如果是新创建的 session,通知父组件
      if (!sessionId) {
        onSessionCreated(res.sessionId)
        refreshSessions()
      }
      const aiMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: res.reply,
        timestamp: Date.now(),
      }
      setMessages((prev) => [...prev, aiMsg])
    } catch {
      message.error('对话请求失败，请确认后端已启动')
    } finally {
      setLoading(false)
    }
  }

  const handleAction = (action: string) => {
    setActiveAction(action)
    const prefix = makePrompt(action)
    const input = document.querySelector('textarea')
    if (input) {
      ;(input as HTMLTextAreaElement).value = prefix
      ;(input as HTMLTextAreaElement).focus()
    }
  }

  const quickActions = [
    { key: 'explain', label: '讲解概念', icon: '📖' },
    { key: 'review', label: '复习主题', icon: '📝' },
    { key: 'quiz', label: '出题自测', icon: '❓' },
    { key: 'compare', label: '对比概念', icon: '⚖️' },
  ]

  return (
    <div className="chat-area">
      {messages.length === 0 && hasWelcome && !loading ? (
        <WelcomeState onQuestion={handleSend} />
      ) : (
        <div className="chat-messages">
          {messages.map((msg) => (
            <div key={msg.id} className={`message-row ${msg.role}`}>
              <div className={`message-avatar ${msg.role}`}>
                {msg.role === 'assistant' ? <RobotOutlined /> : <UserOutlined />}
              </div>
              <div className={`message-bubble ${msg.role}`}>
                {msg.role === 'assistant' ? (
                  <>
                    <MarkdownRenderer content={msg.content} />
                    <SourceCitation content={msg.content} />
                  </>
                ) : (
                  msg.content
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="message-row">
              <div className="message-avatar assistant"><RobotOutlined /></div>
              <div className="message-bubble assistant" style={{ opacity: 0.6 }}>思考中...</div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      )}

      <div className="quick-actions">
        {quickActions.map((a) => (
          <button
            key={a.key}
            className="quick-action-btn"
            style={activeAction === a.key ? {
              borderColor: '#6366f1', color: '#6366f1',
              background: 'rgba(99,102,241,0.06)',
            } : undefined}
            onClick={() => handleAction(a.key)}
          >
            {a.icon} {a.label}
          </button>
        ))}
      </div>

      <ChatInput onSend={handleSend} disabled={loading} />
    </div>
  )
}
