import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input, Button, message } from 'antd'
import { ArrowLeftOutlined, SendOutlined } from '@ant-design/icons'
import { sendMessage } from '../api/client'
import type { LearningMode } from '../types'
import MarkdownRenderer from '../components/MarkdownRenderer'

const MODES: { key: LearningMode; label: string; icon: string; desc: string }[] = [
  { key: 'explain', label: '讲解', icon: '📖', desc: '用笔记把概念讲清楚' },
  { key: 'review', label: '复习', icon: '📝', desc: '生成复习提纲 + 自测题' },
  { key: 'quiz', label: '自测', icon: '❓', desc: '出题检验掌握度' },
  { key: 'compare', label: '对比', icon: '⚖️', desc: '对比两个概念的异同' },
]

const MODE_PROMPTS: Record<LearningMode, (input: string) => string> = {
  explain: (s) => `请用我的学习笔记，把「${s}」这个概念讲清楚。要求：先给一句话定义，再用类比/举例展开，点出常见误区。`,
  review: (s) => `请基于我的笔记，为「${s}」生成复习材料。要求：提纲（分层要点）+ 易错点 + 3 道自测题（附答案）。`,
  quiz: (s) => `请基于我的笔记，围绕「${s}」出 5 道题考我。要求：题型混合（选择/填空/简答），先出题，我答后再给答案与解析。`,
  compare: (s) => {
    const [a, b] = s.split(/[,，\s]+/).filter(Boolean)
    return `请基于我的笔记，对比「${a || s}」与「${b || '相关概念'}」。要求：用表格从定义/原理/适用场景等维度对比，并指出关键区别。`
  },
}

export default function LearningPage() {
  const nav = useNavigate()
  const [mode, setMode] = useState<LearningMode>('explain')
  const [input, setInput] = useState('')
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    const text = input.trim()
    if (!text) return
    setLoading(true)
    setResult('思考中...')
    try {
      const prompt = MODE_PROMPTS[mode](text)
      const res = await sendMessage(prompt)
      setResult(res.reply)
    } catch {
      message.error('请求失败')
      setResult('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <div className="app-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => nav('/')}
          />
          <span style={{ fontWeight: 600, fontSize: 16 }}>学习模式</span>
        </div>
      </div>

      <main className="learning-page">
        {/* 模式选择 */}
        <div className="learning-modes">
          {MODES.map((m) => (
            <button
              key={m.key}
              className={`learning-mode-btn${mode === m.key ? ' active' : ''}`}
              onClick={() => { setMode(m.key); setResult('') }}
            >
              {m.icon} {m.label}
            </button>
          ))}
        </div>
        <p style={{ color: '#6b7280', marginBottom: 16, fontSize: 13 }}>
          {MODES.find((m) => m.key === mode)?.desc}
        </p>

        {/* 输入区 */}
        <div className="learning-input-area">
          <Input
            size="large"
            placeholder={
              mode === 'compare'
                ? '输入两个概念，用空格或逗号分隔'
                : '输入概念或主题名称...'
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={handleSubmit}
            disabled={loading}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSubmit}
            loading={loading}
            disabled={!input.trim()}
            size="large"
          />
        </div>

        {/* 结果 */}
        {result && (
          <div className="learning-result">
            <MarkdownRenderer content={result} />
          </div>
        )}
      </main>
    </div>
  )
}
