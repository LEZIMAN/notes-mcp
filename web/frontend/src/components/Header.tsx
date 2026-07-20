import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Dropdown, message } from 'antd'
import {
  SettingOutlined,
  DashboardOutlined,
  ExperimentOutlined,
  DesktopOutlined,
  CloudOutlined,
  ToolOutlined,
  ReloadOutlined,
  CheckOutlined,
  BookOutlined,
} from '@ant-design/icons'
import { fetchSettings, fetchModels, selectModel, type Settings, type ModelsResponse, type ProviderType } from '../api/settings'

const PROVIDER_ICON: Record<ProviderType, React.ReactNode> = {
  ollama: <DesktopOutlined />,
  openai: <CloudOutlined />,
  custom: <ToolOutlined />,
}

interface Props {
  onOpenSettings?: (tab?: string) => void
  refreshKey?: number
}

export default function Header({ onOpenSettings, refreshKey }: Props) {
  const nav = useNavigate()
  const [provider, setProvider] = useState<ProviderType>('ollama')
  const [currentModel, setCurrentModel] = useState('qwen3:8b')
  const [models, setModels] = useState<ModelsResponse['models']>([])
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [settings, setSettings] = useState<Settings | null>(null)

  const load = async () => {
    try {
      const [s, m] = await Promise.all([fetchSettings(), fetchModels()])
      setSettings(s)
      setProvider(s.activeProvider)
      setCurrentModel(m.current)
      setModels(m.models)
    } catch { /* 静默失败 */ }
  }

  useEffect(() => { load() }, [refreshKey])

  const handleSelectModel = async (model: string) => {
    try {
      await selectModel(model)
      setCurrentModel(model)
      setDropdownOpen(false)
      message.success(`模型已切换为 ${model}`)
    } catch { message.error('切换失败') }
  }

  const modelMenuItems = [
    {
      key: 'header',
      label: (
        <div style={{ fontSize: 11, color: '#9ca3af', padding: '2px 0' }}>
          当前 Provider：{settings?.[provider]?.name || provider}
        </div>
      ),
      disabled: true,
    },
    ...models.map((m) => ({
      key: m.name,
      label: (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, minWidth: 200 }}>
          <span>
            {m.name === currentModel && <CheckOutlined style={{ color: '#6366f1', marginRight: 6 }} />}
            {m.name}
          </span>
          {m.size && <span style={{ fontSize: 11, color: '#9ca3af' }}>{m.size}</span>}
        </div>
      ),
      onClick: () => handleSelectModel(m.name),
    })),
    { type: 'divider' as const },
    {
      key: 'refresh',
      label: <span><ReloadOutlined style={{ marginRight: 6 }} />刷新模型列表</span>,
      onClick: async () => {
        try {
          const m = await fetchModels()
          setModels(m.models)
          setCurrentModel(m.current)
          message.success('模型列表已刷新')
        } catch { message.error('刷新失败') }
      },
    },
    {
      key: 'settings',
      label: <span><SettingOutlined style={{ marginRight: 6 }} />打开模型设置</span>,
      onClick: () => onOpenSettings?.('models'),
    },
  ]

  return (
    <header className="app-header">
      <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
        <div
          className="header-logo"
          style={{ cursor: 'pointer' }}
          onClick={() => nav('/')}
        >
          <BookOutlined style={{ fontSize: 28, color: '#6366f1' }} />
          <div>
            <div>Notes AI</div>
            <div className="header-subtitle">你的 AI 知识助手</div>
          </div>
        </div>
      </div>

      {/* 模型选择器 */}
      <Dropdown
        menu={{ items: modelMenuItems }}
        trigger={['click']}
        open={dropdownOpen}
        onOpenChange={setDropdownOpen}
      >
        <div style={{
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '4px 14px',
          borderRadius: 20,
          background: '#f3f4f6',
          fontSize: 13,
          fontWeight: 500,
          transition: 'all 0.15s',
        }}>
          <span style={{ fontSize: 14 }}>{PROVIDER_ICON[provider]}</span>
          <span>{settings?.[provider]?.name || provider}</span>
          <span style={{ color: '#9ca3af' }}>/</span>
          <span style={{ color: currentModel ? '#6366f1' : '#f59e0b' }}>
            {currentModel || '未选模型'}
          </span>
          <span style={{ fontSize: 10, color: '#9ca3af' }}>▼</span>
        </div>
      </Dropdown>

      <div className="header-right">
        <Button type="text" icon={<ExperimentOutlined />} onClick={() => nav('/learn')} title="学习模式" />
        <Button type="text" icon={<DashboardOutlined />} onClick={() => nav('/dashboard')} title="知识库统计" />
        <Button
          type="text"
          icon={<SettingOutlined />}
          onClick={() => onOpenSettings?.()}
          title="设置"
          style={{ color: '#6b7280' }}
        />
      </div>
    </header>
  )
}
