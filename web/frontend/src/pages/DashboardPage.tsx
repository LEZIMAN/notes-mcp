import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { Button, Spin, Card, Row, Col } from 'antd'
import {
  FileTextOutlined,
  BlockOutlined,
  DatabaseOutlined,
} from '@ant-design/icons'
import { fetchStats } from '../api/client'
import type { Stats } from '../types'

export default function DashboardPage() {
  const nav = useNavigate()
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .finally(() => setLoading(false))
  }, [])

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <div className="app-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => nav('/')}
          />
          <span style={{ fontWeight: 600, fontSize: 16 }}>知识库概览</span>
        </div>
      </div>

      <main className="dashboard">
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 60 }}>
            <Spin size="large" />
          </div>
        ) : stats ? (
          <>
            <div className="dashboard-cards">
              <div className="dashboard-card">
                <FileTextOutlined style={{ fontSize: 28, color: '#6366f1', marginBottom: 8 }} />
                <div className="card-value">{stats.total_files}</div>
                <div className="card-label">笔记数量</div>
              </div>
              <div className="dashboard-card">
                <BlockOutlined style={{ fontSize: 28, color: '#8b5cf6', marginBottom: 8 }} />
                <div className="card-value">{stats.total_chunks}</div>
                <div className="card-label">知识片段</div>
              </div>
              <div className="dashboard-card">
                <DatabaseOutlined style={{ fontSize: 28, color: '#10b981', marginBottom: 8 }} />
                <div className="card-value">{stats.embed_model}</div>
                <div className="card-label">嵌入模型</div>
              </div>
            </div>

            <Card title="笔记目录" style={{ marginBottom: 16 }}>
              {stats.notes_dirs.map((d, i) => (
                <div key={i} style={{ fontFamily: 'monospace', fontSize: 13 }}>
                  📁 {d}
                </div>
              ))}
            </Card>

            <div style={{ color: '#9ca3af', fontSize: 12, textAlign: 'center', marginTop: 32 }}>
              🤖 你的 AI 知识助手正在基于 {stats.total_chunks} 个知识片段回答你的问题
            </div>
          </>
        ) : null}
      </main>
    </div>
  )
}
