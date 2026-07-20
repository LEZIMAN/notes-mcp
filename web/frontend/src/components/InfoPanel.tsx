import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchStats } from '../api/client'
import type { Stats } from '../types'

export default function InfoPanel() {
  const nav = useNavigate()
  const [stats, setStats] = useState<Stats | null>(null)

  useEffect(() => {
    fetchStats().then(setStats).catch(() => {})
  }, [])

  return (
    <aside className="info-panel">
      <div className="info-panel-title">知识状态</div>

      {stats && (
        <>
          <div className="info-card">
            <div className="info-label">笔记数量</div>
            <div className="info-value" style={{ fontSize: 24, color: '#6366f1' }}>
              {stats.total_files}
            </div>
          </div>
          <div className="info-card">
            <div className="info-label">知识片段</div>
            <div className="info-value" style={{ fontSize: 24, color: '#8b5cf6' }}>
              {stats.total_chunks}
            </div>
          </div>
          <div className="info-card">
            <div className="info-label">嵌入模型</div>
            <div className="info-value">{stats.embed_model}</div>
          </div>
          <div className="info-card">
            <div className="info-label">笔记目录</div>
            <div className="info-value" style={{ fontSize: 12, wordBreak: 'break-all' }}>
              {stats.notes_dirs.join('; ')}
            </div>
          </div>
        </>
      )}

      <div style={{ marginTop: 16 }}>
        <div className="info-panel-title">快捷入口</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <a onClick={() => nav('/learn')} style={{ cursor: 'pointer', fontSize: 13 }}>
            📖 学习模式
          </a>
          <a onClick={() => nav('/dashboard')} style={{ cursor: 'pointer', fontSize: 13 }}>
            📊 知识库统计
          </a>
        </div>
      </div>

      <div style={{ marginTop: 'auto', paddingTop: 24, fontSize: 11, color: '#9ca3af', textAlign: 'center' }}>
        AI 不是联网搜索，<br />
        它在理解你的笔记
      </div>
    </aside>
  )
}
