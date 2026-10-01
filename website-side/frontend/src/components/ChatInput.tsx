import React from "react"
import { Paperclip, Send } from "lucide-react"

interface ChatInputProps {
  input: string
  isLoading: boolean
  quickChats?: readonly string[]
  onInputChange: (val: string) => void
  onSubmit: (e: React.FormEvent) => void
  onQuickChatSelect?: (chat: string) => void
}

export const ChatInput: React.FC<ChatInputProps> = ({
  input,
  isLoading,
  quickChats = [],
  onInputChange,
  onSubmit,
  onQuickChatSelect,
}) => {
  return (
    <div className="border-t bg-ab-card-2 p-2 sm:p-2.5">
      {quickChats.length > 0 && (
        <div className="mb-2 overflow-x-auto">
          <div className="flex min-w-max gap-1.5 pb-1">
            {quickChats.map((chat) => (
              <button
                key={chat}
                type="button"
                onClick={() => onQuickChatSelect?.(chat)}
                className="shrink-0 rounded-full border border-ab-border bg-ab-card px-2 py-1 text-[10px] font-medium text-ab-text transition hover:border-ab-accent hover:bg-ab-hover"
              >
                {chat}
              </button>
            ))}
          </div>
        </div>
      )}

      <form onSubmit={onSubmit} className="flex items-center gap-2">
        <button
          type="button"
          aria-label="Attach file"
          className="flex h-10 w-10 items-center justify-center rounded-full border border-ab-border bg-ab-card text-ab-text transition hover:bg-ab-hover"
        >
          <Paperclip className="h-4 w-4" />
        </button>

        <input
          type="text"
          className="flex-1 rounded-full border border-ab-border bg-ab-card px-3 py-2 text-xs text-ab-text focus:ring-2 focus:ring-ab-accent focus:outline-none sm:text-sm"
          placeholder="Ask about properties or work commute..."
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
        />
        <button
          type="submit"
          disabled={isLoading}
          className="flex h-10 w-10 items-center justify-center rounded-full bg-ab-accent text-ab-ink transition hover:bg-ab-accent-hover disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  )
}