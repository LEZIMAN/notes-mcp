import { useEffect, useState } from 'react'
import { Drawer, Tabs, Input, Button, Card, message, Alert, Tag, Spin, Popconfirm } from 'antd'
import {
  DesktopOutlined,
  CloudOutlined,
  ToolOutlined,
  FolderOutlined,
  ReloadOutlined,
  EyeInvisibleOutlined,
  EyeOutlined,
  CheckCircleFilled,
  WarningFilled,
  DeleteOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import type { Settings, ProviderType, ProviderConfig, ModelsResponse } from '../api/settings'
import {
  fetchSettings,
  updateProvider,
  updateNotesDir,
  selectProvider,
  fetchModels,
  selectModel,
  refreshModels,
} from '../api/settings'

const { TextArea } = Input

const PROVIDER_META: Record<ProviderType, { label: string; icon: React.ReactNode; desc: string }> = {
  ollama: { label: 'Ollama 本地', icon: <DesktopOutlined />, desc: '免费、离线、保护隐私' },
  openai: { label: 'OpenAI', icon: <CloudOutlined />, desc: '使用 GPT 系列官方模型' },
  custom: { label: '自定义', icon: <ToolOutlined />, desc: '兼容 DeepSeek、Groq、vLLM、LM Studio 等' },
}

interface Props {
  open: boolean
  onClose: () => void
  onSettingsChange: () => void  // 通知父组件刷新
  defaultTab?: string           // 初始打开哪个 tab
}

export default function SettingsDrawer({ open, onClose, onSettingsChange, defaultTab }: Props) {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(false)

  // 笔记目录
  const [notesDir, setNotesDir] = useState('')
  const [dirList, setDirList] = useState<string[]>([])
  const [newPath, setNewPath] = useState('')
  const [notesSaved, setNotesSaved] = useState(false)
  const [showRestartWarn, setShowRestartWarn] = useState(false)

  // Provider 表单
  const [editingProvider, setEditingProvider] = useState<ProviderType | null>(null)
  const [formBaseUrl, setFormBaseUrl] = useState('')
  const [formApiKey, setFormApiKey] = useState('')
  const [formName, setFormName] = useState('')
  const [showKey, setShowKey] = useState(false)

  // 模型
  const [modelsData, setModelsData] = useState<ModelsResponse | null>(null)
  const [modelsLoading, setModelsLoading] = useState(false)
  const [manualModel, setManualModel] = useState('')

  // 加载设置
  const loadSettings = async () => {
    try {
      const s = await fetchSettings()
      setSettings(s)
      setNotesDir(s.notesDir)
      setDirList(s.notesDir.split(';').map(d => d.trim()).filter(Boolean))
    } catch { message.error('加载设置失败') }
  }

  useEffect(() => { if (open) loadSettings() }, [open])

  // 加载模型
  const loadModels = async () => {
    setModelsLoading(true)
    try {
      const m = await fetchModels()
      setModelsData(m)
    } catch { message.error('加载模型列表失败') }
    finally { setModelsLoading(false) }
  }

  useEffect(() => { if (open) loadModels() }, [open])

  // ---- 笔记目录 ----
  const handleSaveNotesDir = async () => {
    const merged = dirList.join(';')
    setNotesDir(merged)
    setLoading(true)
    try {
      const res = await updateNotesDir(merged)
      if (res.requiresRestart) {
        setShowRestartWarn(true)
      }
      setNotesSaved(true)
      message.success('笔记目录已保存')
      onSettingsChange()
      setTimeout(() => setNotesSaved(false), 3000)
    } catch { message.error('保存失败') }
    finally { setLoading(false) }
  }

  const addPath = () => {
    const p = newPath.trim()
    if (!p) return
    if (dirList.includes(p)) { message.warning('路径已存在'); return }
    setDirList([...dirList, p])
    setNewPath('')
    setShowRestartWarn(false)
  }

  const removePath = (idx: number) => {
    setDirList(dirList.filter((_, i) => i !== idx))
    setShowRestartWarn(false)
  }

  // ---- Provider 切换 ----
  const handleSelectProvider = async (p: ProviderType) => {
    setLoading(true)
    try {
      await selectProvider(p)
      await loadSettings()
      await loadModels()
      message.success(`已切换为 ${PROVIDER_META[p].label}`)
      onSettingsChange()
    } catch { message.error('切换失败') }
    finally { setLoading(false) }
  }

  // ---- Provider 配置编辑 ----
  const startEdit = (p: ProviderType, cfg: ProviderConfig) => {
    setEditingProvider(p)
    setFormName(cfg.name)
    setFormBaseUrl(cfg.baseUrl)
    setFormApiKey(cfg.apiKey.startsWith('****') ? '' : cfg.apiKey)
    setShowKey(false)
  }

  const handleSaveProvider = async () => {
    if (!editingProvider) return
    setLoading(true)
    try {
      await updateProvider(editingProvider, {
        name: formName,
        baseUrl: formBaseUrl,
        apiKey: formApiKey || undefined,  // 空字符串不传,保留原值
        selectedModel: settings?.[editingProvider].selectedModel,
      })
      await loadSettings()
      message.success('配置已保存')
      setEditingProvider(null)
      onSettingsChange()
    } catch { message.error('保存失败') }
    finally { setLoading(false) }
  }

  // ---- 模型 ----
  const handleRefreshModels = async () => {
    setModelsLoading(true)
    try {
      const m = await refreshModels()
      setModelsData(m)
      message.success('模型列表已刷新')
    } catch { message.error('刷新失败') }
    finally { setModelsLoading(false) }
  }

  const handleSelectModel = async (model: string) => {
    setLoading(true)
    try {
      await selectModel(model)
      await loadSettings()
      await loadModels()
      message.success(`模型已切换为 ${model}`)
      onSettingsChange()
    } catch { message.error('切换失败') }
    finally { setLoading(false) }
  }

  // ---- 渲染 ----
  const activeProvider = settings?.activeProvider || 'ollama'

  const renderProviderCards = () => (
    <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
      {(Object.keys(PROVIDER_META) as ProviderType[]).map((key) => {
        const meta = PROVIDER_META[key]
        const isActive = activeProvider === key
        const cfg = settings?.[key]
        const hasKey = cfg?.hasKey || key === 'ollama'

        return (
          <Card
            key={key}
            size="small"
            hoverable
            onClick={() => handleSelectProvider(key)}
            style={{
              flex: 1,
              textAlign: 'center',
              cursor: 'pointer',
              border: isActive ? '2px solid #6366f1' : '1px solid #e5e7eb',
              background: isActive ? 'rgba(99,102,241,0.04)' : '#fff',
              position: 'relative',
            }}
          >
            {isActive && (
              <CheckCircleFilled style={{
                position: 'absolute', top: 6, right: 6,
                color: '#6366f1', fontSize: 16,
              }} />
            )}
            <div style={{ fontSize: 24, marginBottom: 4 }}>{meta.icon}</div>
            <div style={{ fontWeight: 600, fontSize: 13 }}>
              {key === 'custom' && cfg?.name ? cfg.name : meta.label}
            </div>
            <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>{meta.desc}</div>
            {!hasKey && (
              <Tag color="warning" style={{ marginTop: 6, fontSize: 10 }}>缺少 API Key</Tag>
            )}
            {isActive && (
              <Tag color="purple" style={{ marginTop: 6, fontSize: 10 }}>当前使用</Tag>
            )}
          </Card>
        )
      })}
    </div>
  )

  const renderProviderForm = () => {
    if (editingProvider) {
      const isOllama = editingProvider === 'ollama'
      return (
        <div style={{ background: '#f9fafb', borderRadius: 12, padding: 16, marginTop: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 12 }}>
            编辑 {PROVIDER_META[editingProvider].label} 配置
          </div>

          {editingProvider === 'custom' && (
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 12, marginBottom: 4 }}>显示名称</div>
              <Input value={formName} onChange={(e) => setFormName(e.target.value)} />
            </div>
          )}

          <div style={{ marginBottom: 10 }}>
            <div style={{ fontSize: 12, marginBottom: 4 }}>Base URL</div>
            <Input value={formBaseUrl} onChange={(e) => setFormBaseUrl(e.target.value)} />
          </div>

          {!isOllama && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, marginBottom: 4 }}>API Key</div>
              <Input
                type={showKey ? 'text' : 'password'}
                value={formApiKey}
                onChange={(e) => setFormApiKey(e.target.value)}
                placeholder={settings?.[editingProvider].hasKey ? '保留当前密钥（不填则不修改）' : '请输入 API Key'}
                suffix={
                  <Button type="text" size="small"
                    icon={showKey ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                    onClick={() => setShowKey(!showKey)}
                  />
                }
              />
              {settings?.[editingProvider].hasKey && (
                <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 4 }}>
                  保留空白不修改原密钥
                </div>
              )}
            </div>
          )}

          {isOllama && (
            <div style={{ fontSize: 12, color: '#10b981', marginBottom: 12 }}>
              ✓ 本地 Provider，无需 API Key
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <Button onClick={() => setEditingProvider(null)}>取消</Button>
            <Button type="primary" onClick={handleSaveProvider} loading={loading}>保存配置</Button>
          </div>
        </div>
      )
    }

    // 非编辑态: 展示当前配置
    const cfg = settings?.[activeProvider]
    if (!cfg) return null
    const isOllama = activeProvider === 'ollama'

    return (
      <div style={{ background: '#f9fafb', borderRadius: 12, padding: 16, marginTop: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontWeight: 600, fontSize: 13 }}>
            {cfg.name} 配置
          </div>
          <Button size="small" onClick={() => startEdit(activeProvider, cfg)}>编辑</Button>
        </div>
        <div style={{ fontSize: 12, color: '#6b7280', marginTop: 8 }}>
          <div>Base URL: {cfg.baseUrl}</div>
          {!isOllama && (
            <div>API Key: {cfg.hasKey ? `****${cfg.apiKey.slice(-4)}` : '未配置'}</div>
          )}
          <div style={{ marginTop: 4 }}>
            {isOllama ? (
              <Tag color="success">✓ 本地 Provider，无需 API Key</Tag>
            ) : cfg.hasKey ? (
              <Tag color="success">✓ API Key 已配置</Tag>
            ) : (
              <Tag color="warning">⚠️ 未配置 API Key</Tag>
            )}
          </div>
        </div>
      </div>
    )
  }

  const renderModelTab = () => (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontSize: 12, color: '#6b7280' }}>
          当前 Provider：{PROVIDER_META[activeProvider].label}
        </span>
        <Button size="small" icon={<ReloadOutlined spin={modelsLoading} />} onClick={handleRefreshModels}>
          刷新
        </Button>
      </div>

      {/* 当前模型卡片 */}
      {modelsData?.current && (
        <Card size="small" style={{
          marginBottom: 12,
          border: '1px solid #6366f1',
          background: 'rgba(99,102,241,0.04)',
        }}>
          <div style={{ fontSize: 11, color: '#6b7280' }}>当前模型</div>
          <div style={{ fontWeight: 600, fontSize: 15 }}>{modelsData.current}</div>
          <Tag color="purple" style={{ marginTop: 4 }}>✓ 正在使用</Tag>
        </Card>
      )}

      {modelsLoading ? (
        <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div>
      ) : modelsData?.models.length === 0 ? (
        <div>
          <Alert
            type="warning"
            message="暂未获取到可用模型"
            description="请确认 Provider 配置正确，并刷新模型列表。部分 API（如 DeepSeek）不提供模型列表接口，可手动输入模型名。"
            style={{ marginBottom: 12 }}
            action={<Button size="small" onClick={handleRefreshModels}>重新刷新</Button>}
          />
          <div style={{ display: 'flex', gap: 8 }}>
            <Input
              size="small"
              value={manualModel}
              onChange={(e) => setManualModel(e.target.value)}
              placeholder="手动输入模型名，如 deepseek-chat"
              onPressEnter={() => { if (manualModel.trim()) handleSelectModel(manualModel.trim()) }}
            />
            <Button
              size="small"
              type="primary"
              disabled={!manualModel.trim()}
              onClick={() => handleSelectModel(manualModel.trim())}
            >
              使用此模型
            </Button>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {modelsData?.models.map((m) => (
            <Card
              key={m.name}
              size="small"
              hoverable
              onClick={() => handleSelectModel(m.name)}
              style={{
                cursor: 'pointer',
                border: m.name === modelsData.current ? '1px solid #6366f1' : '1px solid #e5e7eb',
                background: m.name === modelsData.current ? 'rgba(99,102,241,0.03)' : '#fff',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontWeight: 500, fontSize: 13 }}>
                    {m.name === modelsData.current && (
                      <CheckCircleFilled style={{ color: '#6366f1', marginRight: 6 }} />
                    )}
                    {m.name}
                  </div>
                  {m.ownedBy && <div style={{ fontSize: 11, color: '#9ca3af' }}>{m.ownedBy}</div>}
                </div>
                {m.size && (
                  <Tag style={{ fontSize: 11 }}>{m.size}</Tag>
                )}
                {m.name === modelsData.current && (
                  <Tag color="purple" style={{ fontSize: 10 }}>当前</Tag>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )

  const tabItems = [
    {
      key: 'notes',
      label: '笔记目录',
      children: (
        <div>
          <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 12 }}>
            配置 AI 可以检索和引用的 Markdown 笔记位置。支持添加文件夹或单独的 .md 文件。
          </div>

          {/* 已添加的目录列表 */}
          <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 6 }}>
            已配置的路径({dirList.length})
          </div>
          {dirList.length === 0 ? (
            <div style={{ fontSize: 12, color: '#9ca3af', padding: '8px 0' }}>
              暂未添加任何目录或文件
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 12 }}>
              {dirList.map((dir, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '6px 10px',
                    background: '#f9fafb',
                    borderRadius: 8,
                    border: '1px solid #e5e7eb',
                    fontSize: 12,
                  }}
                >
                  <FolderOutlined style={{ color: '#6366f1', flexShrink: 0 }} />
                  <span style={{
                    flex: 1,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    fontFamily: 'monospace',
                    fontSize: 11,
                  }}>
                    {dir}
                  </span>
                  <Popconfirm
                    title="移除此路径？"
                    description="仅从列表中移除，不会删除磁盘文件"
                    onConfirm={() => removePath(i)}
                    okText="移除"
                    cancelText="取消"
                  >
                    <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                </div>
              ))}
            </div>
          )}

          {/* 添加新路径 */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <Input
              size="small"
              value={newPath}
              onChange={(e) => setNewPath(e.target.value)}
              onPressEnter={addPath}
              placeholder="d:/Learn/AI/笔记 或 d:/path/file.md"
              style={{ fontFamily: 'monospace', fontSize: 11 }}
            />
            <Button size="small" icon={<PlusOutlined />} onClick={addPath}>
              添加
            </Button>
          </div>
          <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 12 }}>
            支持添加文件夹（扫描其中所有 .md 文件）或单独的 .md 文件路径。
            文件夹支持多层嵌套，系统会自动按目录结构组织。
          </div>

          {showRestartWarn && (
            <Alert
              type="warning"
              icon={<WarningFilled />}
              message="需要重启后端"
              description="笔记目录已经保存，但新的目录需要重启后端服务后才能生效。"
              style={{ marginBottom: 12 }}
              showIcon
            />
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              type="primary"
              onClick={handleSaveNotesDir}
              loading={loading}
              disabled={dirList.length === 0}
            >
              {notesSaved ? '✓ 已保存' : '保存目录'}
            </Button>
          </div>
        </div>
      ),
    },
    {
      key: 'provider',
      label: 'AI Provider',
      children: (
        <div>
          <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 12 }}>
            选择回答问题时使用的模型服务。
          </div>
          {renderProviderCards()}
          {renderProviderForm()}
        </div>
      ),
    },
    {
      key: 'models',
      label: '模型',
      children: renderModelTab(),
    },
  ]

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width={520}
      title={
        <div>
          <div style={{ fontWeight: 600, fontSize: 16 }}>设置</div>
          <div style={{ fontSize: 12, color: '#6b7280', fontWeight: 400 }}>
            配置知识库、AI Provider 和模型
          </div>
        </div>
      }
      styles={{ body: { padding: '16px 20px' } }}
    >
      <Tabs
        items={tabItems}
        defaultActiveKey={defaultTab || 'notes'}
      />
    </Drawer>
  )
}
