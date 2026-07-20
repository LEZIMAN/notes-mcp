import { useState } from 'react'
import { Input, Button } from 'antd'
import { SendOutlined } from '@ant-design/icons'

const { TextArea } = Input

interface Props {
  onSend: (msg: string) => void
  disabled?: boolean
}

export default function ChatInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState('')

  const handleSend = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
  }

  return (
    <div className="chat-input-area">
      <div className="chat-input-container">
        <TextArea
          className="chat-input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault()
              handleSend()
            }
          }}
          placeholder="请输入你的问题...（Enter 发送，Shift+Enter 换行）"
          autoSize={{ minRows: 1, maxRows: 5 }}
          disabled={disabled}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          shape="circle"
          size="large"
        />
      </div>
    </div>
  )
}
