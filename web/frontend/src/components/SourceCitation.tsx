import { useNavigate } from 'react-router-dom'
import { LinkOutlined } from '@ant-design/icons'

interface Props {
  sources: string[]
}

/** 从 AI 回复文本中提取来源引用（格式: *来源: path*）并渲染为可点击链接 */
function extractSources(content: string): {
  body: string
  sources: { title: string; path: string }[]
} {
  const lines = content.split('\n')
  const sourceStart = lines.findIndex((l) =>
    /^\*来源[：:]/.test(l.trim()),
  )

  if (sourceStart < 0) return { body: content, sources: [] }

  const body = lines.slice(0, sourceStart).join('\n').trim()
  const sources: { title: string; path: string }[] = []

  for (let i = sourceStart; i < lines.length; i++) {
    const line = lines[i].replace(/^\*(来源[：:]?)?/, '').trim()
    if (!line || /^来源/.test(line)) continue
    // 提取文件名（去掉路径前缀和 .md 后缀）
    const match = line.match(/([^\\/:*?"<>|]+)\.md/)
    if (match) {
      sources.push({ title: match[1], path: line })
    }
  }

  return { body, sources }
}

export default function SourceCitation({ content }: { content: string }) {
  const nav = useNavigate()
  const { sources } = extractSources(content)

  if (sources.length === 0) return null

  return (
    <div className="message-sources">
      <div style={{ fontWeight: 500, marginBottom: 4 }}>📚 来源引用</div>
      {sources.map((s, i) => (
        <div
          key={i}
          className="source-link"
          onClick={() => nav(`/note/${encodeURIComponent(s.title)}`)}
        >
          <LinkOutlined />
          <span>{s.title}.md</span>
        </div>
      ))}
    </div>
  )
}
