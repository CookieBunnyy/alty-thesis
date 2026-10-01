import React from "react"
import { AlertCircle, Eye, MapPin, Bed, Bath } from "lucide-react"
import type { ChatMessage, Property } from "../types"

const formatDayLabel = (value?: string) => {
  if (!value) return ""
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""

  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
  }).format(date)
}

const formatTimeLabel = (value?: string) => {
  if (!value) return ""
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""

  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date)
}

interface ChatMessageListProps {
  messages: ChatMessage[]
  selectedProperty: Property | null
  isLoading: boolean
  chatEndRef: React.RefObject<HTMLDivElement | null>
  onSelectProperty: (prop: Property) => void
}

export const ChatMessageList: React.FC<ChatMessageListProps> = ({
  messages,
  selectedProperty,
  isLoading,
  chatEndRef,
  onSelectProperty,
}) => {
  return (
    <div className="h-full min-h-0 flex-1 space-y-4 overflow-y-auto p-3 sm:p-4">
      {messages.map((msg, index) => {
        const previousMessage = messages[index - 1]
        const shouldShowDate =
          index === 0 ||
          (previousMessage?.timestamp && msg.timestamp && formatDayLabel(previousMessage.timestamp) !== formatDayLabel(msg.timestamp))

        return (
          <React.Fragment key={msg.id}>
            {shouldShowDate && msg.timestamp && (
              <div className="flex justify-center">
                <div className="rounded-full border border-ab-border bg-ab-hover px-3 py-1 text-[11px] font-medium text-ab-text">
                  {formatDayLabel(msg.timestamp)}
                </div>
              </div>
            )}
            <div
              className={`flex flex-col ${
                msg.sender === "user" ? "items-end" : "items-start"
              }`}
            >
              <div
                className={`max-w-[88%] rounded-2xl px-4 py-3 text-xs shadow-sm sm:text-sm ${
                  msg.sender === "user"
                    ? "rounded-br-none bg-ab-sidebar text-ab-text"
                    : msg.status === "rejected"
                      ? "rounded-bl-none border border-ab-danger/40 bg-ab-danger/10 text-ab-danger"
                      : msg.status === "clarification_needed"
                        ? "rounded-bl-none border border-ab-warning/40 bg-ab-warning/10 text-ab-warning"
                        : "rounded-bl-none bg-ab-hover text-ab-text"
                }`}
              >
                {msg.status === "clarification_needed" && (
                  <div className="mb-1 flex items-center space-x-1 font-medium text-ab-warning">
                    <AlertCircle className="h-4 w-4" />
                    <span>More details needed</span>
                  </div>
                )}
                <p className="leading-relaxed">{msg.text}</p>
              </div>

              {msg.timestamp && (
                <div className={`mt-1 text-[10px] text-ab-muted ${msg.sender === "user" ? "mr-1" : "ml-1"}`}>
                  {formatTimeLabel(msg.timestamp)}
                </div>
              )}

              {/* Inline Property Suggestions */}
              {msg.recommendations && msg.recommendations.length > 0 && (
                <div className="mt-3 w-full space-y-2">
                  {msg.recommendations.map((prop) => (
                    <div
                      key={prop.listing_id}
                      onClick={() => onSelectProperty(prop)}
                      className={`cursor-pointer rounded-lg border p-3 transition-all hover:shadow-md ${
                        selectedProperty?.listing_id === prop.listing_id
                          ? "border-ab-accent bg-ab-hover"
                          : "border-ab-border bg-ab-card hover:border-ab-border"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <h4 className="text-xs leading-snug font-semibold text-ab-text sm:text-sm">
                          {prop.title}
                        </h4>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            onSelectProperty(prop)
                          }}
                          className="ml-2 flex shrink-0 items-center rounded-md bg-ab-hover px-2 py-1 text-[11px] font-medium text-ab-text hover:underline"
                        >
                          <Eye className="mr-1 h-3 w-3" /> View
                        </button>
                      </div>

                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-ab-muted">
                        <span className="flex items-center">
                          <MapPin className="mr-1 h-3 w-3 text-ab-faint" />
                          {prop.village_name}
                        </span>
                        <span className="flex items-center">
                          <Bed className="mr-1 h-3 w-3 text-ab-faint" />
                          {prop.num_bedrooms} Bed
                        </span>
                        <span className="flex items-center">
                          <Bath className="mr-1 h-3 w-3 text-ab-faint" />
                          {prop.num_bathrooms} Bath
                        </span>
                      </div>

                      <div className="mt-2 flex items-center justify-between">
                        <p className="text-sm font-bold text-ab-text">
                          ₱{prop.price_total.toLocaleString()}
                        </p>
                        {prop.commute_info && (
                          <span className="rounded-full border border-ab-border bg-ab-card-2 px-2 py-0.5 text-[10px] font-semibold text-ab-muted">
                            ⏱️ {prop.commute_info.duration_mins} mins away
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </React.Fragment>
        )
      })}
      {isLoading && (
        <div className="animate-pulse text-xs text-ab-faint">
          Assistant is typing...
        </div>
      )}
      <div ref={chatEndRef} />
    </div>
  )
}