import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button, Spin, message } from 'antd'
import { ArrowLeftOutlined, ExperimentOutlined } from '@ant-design/icons'
import { fetchNote, fetchTopics, sendMessage } from '../api/client'
import type { ApiNoteResponse } from '../types'
import MarkdownRenderer from '../components/MarkdownRenderer'

export default function NoteDetailPage() {
  const { title } = useParams<{ title: string }>()
  const nav = useNavigate()
  const [note, setNote] = useState<ApiNoteResponse | null>(null)
  const [topics, setTopics] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [aiResult, setAiResult] = useState('')

  useEffect(() => {
    if (!title) return
    setLoading(true)
    Promise.all([
      fetchNote(decodeURIComponent(title)),
      fetchTopics(),
    ])
      .then(([n, t]) => {
        setNote(n)
        setTopics(
          t
            .split('\n')
            .map((l) => l.replace(/^- /, '').trim())
            .filter(Boolean),
        )
      })
      .catch(() => message.error('加载笔记失败'))
      .finally(() => setLoading(false))
  }, [title])

  const handleAiAction = async (action: string) => {
    if (!title) return
    setAiResult('思考中...')
    try {
      const prompts: Record<string, string> = {
        summarize: `请用中文总结以下笔记的核心要点：\n\n${note?.content?.slice(0, 3000) || ''}`,
        mindmap: `请基于这篇笔记生成一个思维导图（用 markdown 列表层级表示）：\n\n${note?.content?.slice(0, 3000) || ''}`,
        quiz: `请基于这篇笔记出 5 道测试题，附答案和解析：\n\n${note?.content?.slice(0, 3000) || ''}`,
        explain: `请解释这篇笔记中的难点概念，用易懂的方式讲清楚：\n\n${note?.content?.slice(0, 3000) || ''}`,
      }
      const prompt = prompts[action] || ''
      const res = await sendMessage(prompt)
      setAiResult(res.reply)
    } catch {
      setAiResult('AI 操作失败，请确认后端已启动')
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* 简易顶部栏 */}
      <div className="app-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => nav('/')}
          />
          <span style={{ fontWeight: 600 }}>{note?.title || title}</span>
        </div>
      </div>

      <div className="note-detail-layout">
        {/* 左侧目录 */}
        <aside className="note-toc">
          <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>笔记目录</div>
          {topics.slice(0, 30).map((t) => (
            <div
              key={t}
              style={{
                padding: '3px 8px',
                borderRadius: 6,
                cursor: 'pointer',
                fontSize: 12,
                color: t === (title ? decodeURIComponent(title) : '') ? '#6366f1' : '#6b7280',
                background: t === (title ? decodeURIComponent(title) : '') ? 'rgba(99,102,241,0.06)' : 'transparent',
              }}
              onClick={() => nav(`/note/${encodeURIComponent(t)}`)}
            >
              {t.length > 22 ? t.slice(0, 22) + '...' : t}
            </div>
          ))}
        </aside>

        {/* 中央 Markdown */}
        <main className="note-content">
          <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 16 }}>
            最后编辑: {new Date().toLocaleDateString('zh-CN')}
          </div>
          <MarkdownRenderer content={note?.content || '*无内容*'} />
        </main>

        {/* 右侧 AI 操作 */}
        <aside className="note-actions">
          <div className="info-panel-title">AI 工具</div>
          {[
            { key: 'explain', label: '解释难点', icon: '💡' },
            { key: 'summarize', label: '总结本文', icon: '📋' },
            { key: 'mindmap', label: '思维导图', icon: '🗺️' },
            { key: 'quiz', label: '出测试题', icon: '❓' },
          ].map((a) => (
            <Button
              key={a.key}
              block
              onClick={() => handleAiAction(a.key)}
              style={{ textAlign: 'left' }}
            >
              {a.icon} {a.label}
            </Button>
          ))}

          {aiResult && (
            <div className="info-card" style={{ marginTop: 12, maxHeight: 400, overflowY: 'auto' }}>
              <MarkdownRenderer content={aiResult} />
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
