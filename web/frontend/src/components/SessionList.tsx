import { useEffect, useState } from 'react'
import { Button, Popconfirm, message } from 'antd'
import { PlusOutlined, DeleteOutlined, MessageOutlined } from '@ant-design/icons'
import { fetchSessions, deleteSessionApi, type SessionInfo } from '../api/client'

interface Props {
  activeSessionId: string
  onSelect: (id: string) => void
  onNew: () => void
  refreshKey: number
}

export default function SessionList({ activeSessionId, onSelect, onNew, refreshKey }: Props) {
  const [sessions, setSessions] = useState<SessionInfo[]>([])

  useEffect(() => {
    fetchSessions()
      .then((d) => setSessions(d.sessions))
      .catch(() => {})
  }, [refreshKey])

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await deleteSessionApi(id)
      setSessions((prev) => prev.filter((s) => s.id !== id))
      message.success('已删除')
    } catch { message.error('删除失败') }
  }

  return (
    <div style={{ padding: '8px 12px', borderBottom: '1px solid #e5e7eb' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#6b7280' }}>对话记录</span>
        <Button type="text" size="small" icon={<PlusOutlined />} onClick={onNew} title="新对话" />
      </div>
      <div style={{ maxHeight: 200, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {sessions.length === 0 ? (
          <div style={{ fontSize: 11, color: '#9ca3af', textAlign: 'center', padding: 8 }}>暂无对话记录</div>
        ) : (
          sessions.map((s) => (
            <div
              key={s.id}
              onClick={() => onSelect(s.id)}
              style={{
                padding: '6px 8px',
                borderRadius: 6,
                cursor: 'pointer',
                fontSize: 12,
                background: s.id === activeSessionId ? 'rgba(99,102,241,0.08)' : 'transparent',
                border: s.id === activeSessionId ? '1px solid rgba(99,102,241,0.3)' : '1px solid transparent',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                transition: 'all 0.1s',
              }}
            >
              <div style={{ overflow: 'hidden', flex: 1 }}>
                <div style={{
                  fontWeight: s.id === activeSessionId ? 600 : 400,
                  color: s.id === activeSessionId ? '#6366f1' : '#374151',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}>
                  <MessageOutlined style={{ fontSize: 10, marginRight: 4 }} />
                  {s.title}
                </div>
                {s.preview && (
                  <div style={{ fontSize: 10, color: '#9ca3af', marginTop: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {s.preview}
                  </div>
                )}
              </div>
              <Popconfirm
                title="删除此对话？"
                onConfirm={(e) => handleDelete(s.id, e as unknown as React.MouseEvent)}
                okText="删除"
                cancelText="取消"
              >
                <Button type="text" size="small" danger icon={<DeleteOutlined />}
                  onClick={(e) => e.stopPropagation()}
                />
              </Popconfirm>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
