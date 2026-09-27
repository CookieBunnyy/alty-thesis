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
                <div className="rounded-full border border-[#d8d1c8] bg-[#f0efe9] px-3 py-1 text-[11px] font-medium text-[#183c32]">
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
                    ? "rounded-br-none bg-[#0d3529] text-[#f3efe7]"
                    : msg.status === "rejected"
                      ? "rounded-bl-none border border-red-200 bg-red-50 text-red-800"
                      : msg.status === "clarification_needed"
                        ? "rounded-bl-none border border-amber-200 bg-amber-50 text-amber-900"
                        : "rounded-bl-none bg-[#edf0ed] text-[#183c32]"
                }`}
              >
                {msg.status === "clarification_needed" && (
                  <div className="mb-1 flex items-center space-x-1 font-medium text-amber-700">
                    <AlertCircle className="h-4 w-4" />
                    <span>More details needed</span>
                  </div>
                )}
                <p className="leading-relaxed">{msg.text}</p>
              </div>

              {msg.timestamp && (
                <div className={`mt-1 text-[10px] text-slate-500 ${msg.sender === "user" ? "mr-1" : "ml-1"}`}>
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
                          ? "border-[#123f33] bg-[#edf0ed]"
                          : "border-[#d8d1c8] bg-[#f9f6f2] hover:border-[#bfc7c1]"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <h4 className="text-xs leading-snug font-semibold text-slate-900 sm:text-sm">
                          {prop.title}
                        </h4>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            onSelectProperty(prop)
                          }}
                          className="ml-2 flex shrink-0 items-center rounded-md bg-[#dfe7e2] px-2 py-1 text-[11px] font-medium text-[#123f33] hover:underline"
                        >
                          <Eye className="mr-1 h-3 w-3" /> View
                        </button>
                      </div>

                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                        <span className="flex items-center">
                          <MapPin className="mr-1 h-3 w-3 text-slate-400" />
                          {prop.village_name}
                        </span>
                        <span className="flex items-center">
                          <Bed className="mr-1 h-3 w-3 text-slate-400" />
                          {prop.num_bedrooms} Bed
                        </span>
                        <span className="flex items-center">
                          <Bath className="mr-1 h-3 w-3 text-slate-400" />
                          {prop.num_bathrooms} Bath
                        </span>
                      </div>

                      <div className="mt-2 flex items-center justify-between">
                        <p className="text-sm font-bold text-[#123f33]">
                          ₱{prop.price_total.toLocaleString()}
                        </p>
                        {prop.commute_info && (
                          <span className="rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
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
        <div className="animate-pulse text-xs text-slate-400">
          Assistant is typing...
        </div>
      )}
      <div ref={chatEndRef} />
    </div>
  )
}