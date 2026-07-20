import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input, Spin, message } from 'antd'
import { SearchOutlined, FileTextOutlined, FolderOutlined, FolderOpenOutlined } from '@ant-design/icons'
import { fetchStats } from '../api/client'
import type { Stats } from '../types'

/** API 返回的树节点 */
interface TreeNode {
  name: string
  path: string
  type: 'folder' | 'file'
  title?: string
  children?: TreeNode[]
  error?: string
}

interface ApiTreeResponse {
  notesDir: string
  trees: TreeNode[]
}

async function fetchTree(): Promise<ApiTreeResponse> {
  const res = await fetch('/api/notes/tree')
  if (!res.ok) throw new Error('加载文件树失败')
  return res.json()
}

/** 过滤树：保留文件名/标题匹配的节点 */
function filterTree(node: TreeNode, keyword: string): TreeNode | null {
  if (keyword === '') return node
  const kw = keyword.toLowerCase()
  if (node.type === 'file') {
    const matchName = node.name.toLowerCase().includes(kw)
    const matchTitle = (node.title || '').toLowerCase().includes(kw)
    if (matchName || matchTitle) return node
    return null
  }
  // folder: 递归过滤子节点
  const filtered = (node.children || [])
    .map((c) => filterTree(c, kw))
    .filter(Boolean) as TreeNode[]
  if (filtered.length > 0) {
    return { ...node, children: filtered }
  }
  return null
}

/** 递归渲染树节点 */
function TreeItem({
  node,
  depth,
  onSelectNote,
}: {
  node: TreeNode
  depth: number
  onSelectNote: (title: string) => void
}) {
  const [expanded, setExpanded] = useState(depth === 0) // 根节点默认展开
  const nav = useNavigate()

  if (node.type === 'file') {
    return (
      <div
        className="tree-file"
        style={{ paddingLeft: 12 + depth * 14 }}
        onClick={() => onSelectNote(node.title || node.name.replace('.md', ''))}
      >
        <FileTextOutlined style={{ fontSize: 12, flexShrink: 0 }} />
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {node.title || node.name.replace('.md', '')}
        </span>
      </div>
    )
  }

  // folder
  const hasChildren = node.children && node.children.length > 0
  return (
    <div>
      <div
        className="tree-file"
        style={{ fontWeight: 600, fontSize: 12, paddingLeft: 4 + depth * 12 }}
        onClick={() => hasChildren && setExpanded(!expanded)}
      >
        {expanded ? (
          <FolderOpenOutlined style={{ fontSize: 12 }} />
        ) : (
          <FolderOutlined style={{ fontSize: 12 }} />
        )}
        <span>{node.name}</span>
        {hasChildren && (
          <span style={{ fontSize: 10, color: '#9ca3af', marginLeft: 'auto' }}>
            {node.children.length}
          </span>
        )}
      </div>
      {expanded && hasChildren && (
        <div>
          {node.children!.map((child, i) => (
            <TreeItem
              key={child.path || i}
              node={filterTree(child, '') || child}
              depth={depth + 1}
              onSelectNote={onSelectNote}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface Props {
  children?: React.ReactNode
}

export default function Sidebar({ children }: Props) {
  const nav = useNavigate()
  const [trees, setTrees] = useState<TreeNode[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  useEffect(() => {
    Promise.all([fetchTree(), fetchStats()])
      .then(([treeData, statsData]) => {
        setTrees(treeData.trees || [])
        setStats(statsData)
      })
      .catch(() => message.warning('加载知识库信息失败'))
      .finally(() => setLoading(false))
  }, [])

  const handleSelectNote = (title: string) => {
    nav(`/note/${encodeURIComponent(title)}`)
  }

  const filteredTrees = search
    ? trees
        .map((t) => filterTree(t, search))
        .filter(Boolean) as TreeNode[]
    : trees

  if (loading) {
    return (
      <aside className="sidebar" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <Spin size="small" />
      </aside>
    )
  }

  return (
    <aside className="sidebar">
      {children}

      <div className="sidebar-search">
        <Input
          prefix={<SearchOutlined />}
          placeholder="搜索笔记..."
          size="small"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          allowClear
        />
      </div>

      <div className="sidebar-tree">
        {filteredTrees.length === 0 && search && (
          <div style={{ fontSize: 12, color: '#9ca3af', textAlign: 'center', padding: 16 }}>
            未找到匹配的笔记
          </div>
        )}
        {filteredTrees.map((root, i) => (
          <TreeItem
            key={root.path || i}
            node={root}
            depth={0}
            onSelectNote={handleSelectNote}
          />
        ))}
      </div>

      {stats && (
        <div className="sidebar-stats">
          <div style={{ fontWeight: 600, marginBottom: 8, color: '#111827' }}>
            知识库状态
          </div>
          <div className="stat-row">
            <span>📄 笔记</span>
            <span className="stat-label">{stats.total_files} 篇</span>
          </div>
          <div className="stat-row">
            <span>🧩 片段</span>
            <span className="stat-label">{stats.total_chunks}</span>
          </div>
          <div className="stat-row">
            <span>🧠 模型</span>
            <span>{stats.embed_model}</span>
          </div>
        </div>
      )}
    </aside>
  )
}
