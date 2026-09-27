import React from "react"
import { Send } from "lucide-react"

interface ChatInputProps {
  input: string
  isLoading: boolean
  onInputChange: (val: string) => void
  onSubmit: (e: React.FormEvent) => void
}

export const ChatInput: React.FC<ChatInputProps> = ({
  input,
  isLoading,
  onInputChange,
  onSubmit,
}) => {
  return (
    <form
      onSubmit={onSubmit}
      className="flex space-x-2 border-t bg-white p-2.5 sm:p-3"
    >
      <input
        type="text"
        className="flex-1 rounded-lg border border-[#d8d1c8] bg-[#f9f6f2] px-3 py-2 text-xs text-[#183c32] focus:ring-2 focus:ring-[#123f33] focus:outline-none sm:text-sm"
        placeholder="Ask about properties or work commute..."
        value={input}
        onChange={(e) => onInputChange(e.target.value)}
      />
      <button
        type="submit"
        disabled={isLoading}
        className="rounded-lg bg-[#0d3529] px-3.5 py-2 text-[#f3efe7] transition hover:bg-[#173f32] disabled:opacity-50"
      >
        <Send className="h-4 w-4" />
      </button>
    </form>
  )
}