// The assistant conversation, kept for this browsing session only: it
// survives moving between pages and reloads, and is forgotten when the tab or
// browser is closed (sessionStorage) — like the workplace (lib/workplace.ts).
import type { ChatMessage, Property } from "@/types"

const KEY = "alty-chat"

export interface ChatSession {
  messages: ChatMessage[]
  /** Recommendations shown on the map when the visitor left, or null. */
  recommendations: Property[] | null
}

export function loadChatSession(): ChatSession | null {
  try {
    const saved = JSON.parse(window.sessionStorage.getItem(KEY) ?? "null")
    return saved && Array.isArray(saved.messages) && saved.messages.length
      ? { messages: saved.messages, recommendations: Array.isArray(saved.recommendations) ? saved.recommendations : null }
      : null
  } catch {
    return null
  }
}

export function saveChatSession(session: ChatSession) {
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(session))
  } catch {
    /* storage blocked or full: the chat lasts while this page is open */
  }
}
