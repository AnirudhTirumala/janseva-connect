import { createContext, useContext, useState, useEffect } from 'react'

const ChatContext = createContext(null)

const STORAGE_KEY = 'pp_chat_messages'

const INITIAL_MESSAGE = {
  role: 'assistant',
  content: "Hi, I'm the JanSeva Connect AI Assistant. Ask me about welfare schemes, eligibility, required documents, or how to use this portal.",
}

function loadInitialMessages() {
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      if (Array.isArray(parsed) && parsed.length > 0) return parsed
    }
  } catch {
    // corrupted storage - fall through to default
  }
  return [INITIAL_MESSAGE]
}

export function ChatProvider({ children }) {
  const [messages, setMessagesState] = useState(loadInitialMessages)

  // Wrap setMessages so every update also persists to sessionStorage -
  // this means the conversation survives a browser refresh too, not just
  // in-app navigation between pages, while still being scoped to this tab
  // and cleared automatically when the tab closes.
  const setMessages = (updater) => {
    setMessagesState((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater
      try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      } catch {
        // sessionStorage unavailable/full - chat still works in-memory for this session
      }
      return next
    })
  }

  const clearChat = () => {
    setMessagesState([INITIAL_MESSAGE])
    try {
      sessionStorage.removeItem(STORAGE_KEY)
    } catch {
      // ignore
    }
  }

  return (
    <ChatContext.Provider value={{ messages, setMessages, clearChat }}>
      {children}
    </ChatContext.Provider>
  )
}

export function useChat() {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChat must be used within ChatProvider')
  return ctx
}
