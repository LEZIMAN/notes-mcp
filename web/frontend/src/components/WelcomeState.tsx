import { useEffect, useState } from 'react'

interface Props {
  onQuestion: (q: string) => void
}

/** 从知识库标题生成问题模板 */
function titlesToQuestions(titles: string[]): string[] {
  if (titles.length === 0) return []
  const shuffled = [...titles].sort(() => Math.random() - 0.5)
  const picked = shuffled.slice(0, Math.min(4, shuffled.length))
  const patterns = [
    (t: string) => `解释一下「${t}」`,
    (t: string) => `帮我复习「${t}」`,
    (t: string) => `「${t}」的核心概念是什么？`,
    (t: string) => `关于「${t}」，我需要掌握哪些要点？`,
  ]
  return picked.map((t, i) => patterns[i % patterns.length](t))
}

/** 从树结构中递归提取所有文件标题 */
function extractTitles(nodes: TreeNode[]): string[] {
  const titles: string[] = []
  const walk = (list: TreeNode[]) => {
    for (const n of list) {
      if (n.type === 'file' && n.title) titles.push(n.title)
      if (n.children) walk(n.children)
    }
  }
  walk(nodes)
  return titles
}

interface TreeNode {
  name: string
  type: string
  title?: string
  children?: TreeNode[]
}

async function loadQuestions(): Promise<string[]> {
  try {
    const res = await fetch('/api/notes/tree')
    const data = await res.json()
    const titles = extractTitles(data.trees || [])
    return titlesToQuestions(titles)
  } catch {
    return []
  }
}

const FALLBACK_QUESTIONS = [
  '我的笔记里有哪些内容？',
  '解释一下我最近学的概念',
  '帮我复习笔记中的重点',
  '对比笔记中的两个关键概念',
]

export default function WelcomeState({ onQuestion }: Props) {
  const [questions, setQuestions] = useState<string[]>([])

  useEffect(() => {
    loadQuestions().then((qs) => {
      setQuestions(qs.length > 0 ? qs : FALLBACK_QUESTIONS)
    })
  }, [])

  return (
    <div className="chat-welcome">
      <div style={{ fontSize: 56, marginBottom: 12 }}>📖</div>
      <h2>你好，我是你的 AI 知识助手 👋</h2>
      <p>你的笔记已经准备好了，可以问我任何问题</p>
      <div className="welcome-questions">
        {questions.map((q) => (
          <button
            key={q}
            className="welcome-question-btn"
            onClick={() => onQuestion(q)}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}
