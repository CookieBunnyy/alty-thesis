import React, { useState, useRef, useEffect, useMemo } from "react"
import { Bath, Bed, Building2, ChevronLeft, MapPin, MessageCircleMore, Search, Sparkles, X } from "lucide-react"
import { PropertyMap } from "./components/MapContainer"
import { PropertyDetailModal } from "./components/PropertyDetailModal"
import { Header } from "./components/Header"
import { ChatMessageList } from "./components/ChatMessageList"
import { ChatInput } from "./components/ChatInput"
import type { ChatMessage, Property, LocationPoint } from "./types"

const BACKEND_URL = "https://alty-thesis.onrender.com"
const LISTING_FILTERS = ["All", "Apartment", "Villa", "Duplex", "Warehouse"] as const
const QUICK_CHAT_SUGGESTIONS = [
  "Find a condo in BGC under 8k monthly",
  "Show me 3-bedroom houses in Alabang",
  "Properties near my office in Makati",
  "I want a duplex with a 2M down payment",
  "Apartment in Taguig within 30 minutes commute",
  "Affordable studio in Pasig",
] as const

type ListingFilter = (typeof LISTING_FILTERS)[number]

const matchesListingFilter = (property: Property, filter: ListingFilter) => {
  if (filter === "All") return true

  const haystack = `${property.category ?? ""} ${property.title ?? ""} ${property.village_name ?? ""}`.toLowerCase()

  switch (filter) {
    case "Apartment":
      return haystack.includes("apartment") || haystack.includes("condo") || haystack.includes("studio")
    case "Villa":
      return haystack.includes("villa") || haystack.includes("house") || haystack.includes("subdivision")
    case "Duplex":
      return haystack.includes("duplex") || haystack.includes("townhouse") || haystack.includes("town house")
    case "Warehouse":
      return haystack.includes("warehouse") || haystack.includes("industrial")
    default:
      return true
  }
}

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "1",
      sender: "assistant",
      text: "Hello! I am your real estate assistant. What is your budget and location preference?",
      timestamp: new Date().toISOString(),
    },
  ])
  const [input, setInput] = useState<string>("")
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [activeProperties, setActiveProperties] = useState<Property[]>([])
  const [selectedProperty, setSelectedProperty] = useState<Property | null>(null)
  const [workplaceLocation, setWorkplaceLocation] = useState<LocationPoint | null>(null)
  const [activeTab, setActiveTab] = useState<"chat" | "map">("map")
  const [previewProperty, setPreviewProperty] = useState<Property | null>(null)
  const [isListingsOpen, setIsListingsOpen] = useState(() => (typeof window !== "undefined" ? window.innerWidth >= 768 : true))
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [isWorkplaceModalOpen, setIsWorkplaceModalOpen] = useState(false)
  const [workplaceInput, setWorkplaceInput] = useState("")
  const [quickChats, setQuickChats] = useState<string[]>([...QUICK_CHAT_SUGGESTIONS])
  const [activeFilter, setActiveFilter] = useState<ListingFilter>("All")
  const [searchTerm, setSearchTerm] = useState("")
  const [isMobileView, setIsMobileView] = useState(() => (typeof window !== "undefined" ? window.innerWidth < 768 : false))

  const chatEndRef = useRef<HTMLDivElement | null>(null)

  const filteredProperties = useMemo(
    () =>
      activeProperties.filter((property) => {
        const matchesCategory = matchesListingFilter(property, activeFilter)
        const query = searchTerm.trim().toLowerCase()

        if (!query) return matchesCategory

        const haystack = `${property.title ?? ""} ${property.village_name ?? ""} ${property.category ?? ""}`.toLowerCase()
        return matchesCategory && haystack.includes(query)
      }),
    [activeProperties, activeFilter, searchTerm]
  )

  const hasActiveProperties = activeProperties.length > 0
  const hasPropertyResults = filteredProperties.length > 0

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isChatOpen])

  useEffect(() => {
    if (typeof window === "undefined") return

    const mediaQuery = window.matchMedia("(max-width: 767px)")

    const updateViewport = () => {
      const mobile = mediaQuery.matches
      setIsMobileView(mobile)

      if (mobile) {
        setIsChatOpen(false)
        setIsListingsOpen(false)
        setActiveTab("map")
      }
    }

    updateViewport()
    mediaQuery.addEventListener("change", updateViewport)

    return () => mediaQuery.removeEventListener("change", updateViewport)
  }, [])

  useEffect(() => {
    fetch(`${BACKEND_URL}/properties`)
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setActiveProperties([])
        }
      })
      .catch((err) => console.error("Failed to load initial properties:", err))
  }, [])

  const handleSearchProperties = async (overrideQuery?: string) => {
    const query = (overrideQuery ?? searchTerm).trim()

    if (!query) {
      setActiveProperties([])
      setSelectedProperty(null)
      return
    }

    try {
      const response = await fetch(`${BACKEND_URL}/properties`)
      const data = await response.json()

      if (!Array.isArray(data)) {
        setActiveProperties([])
        return
      }

      const normalizedQuery = query.toLowerCase()
      const matches = data.filter((property) => {
        const haystack = `${property.title ?? ""} ${property.village_name ?? ""} ${property.category ?? ""}`.toLowerCase()
        return haystack.includes(normalizedQuery)
      })

      setActiveProperties(matches)
      setSelectedProperty(null)
    } catch (error) {
      console.error("Failed to search properties:", error)
      setActiveProperties([])
    }
  }

  const sendChatMessage = async (textMessage: string) => {
    if (!textMessage.trim() || isLoading) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      sender: "user",
      text: textMessage,
      timestamp: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)
    setIsChatOpen(true)

    try {
      const response = await fetch(`${BACKEND_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage.text,
          workplace_lat: workplaceLocation?.lat || null,
          workplace_lng: workplaceLocation?.lng || null,
          workplace_name: workplaceLocation?.name || null,
        }),
      })

      const data = await response.json()
      if (data.detected_workplace) setWorkplaceLocation(data.detected_workplace)

      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: "assistant",
          text: data.reply,
          timestamp: new Date().toISOString(),
          status: data.status,
          recommendations: data.recommendations || [],
        },
      ])

      if (data.recommendations?.length > 0)
        setActiveProperties(data.recommendations)
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: "assistant",
          text: "Connection error. Please ensure the backend server is running.",
          timestamp: new Date().toISOString(),
          status: "rejected",
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault()
    sendChatMessage(input)
    setInput("")
  }

  const handleQuickChatSelect = (quickChat: string) => {
    setQuickChats((prev) => prev.filter((chat) => chat !== quickChat))
    setInput("")
    setActiveTab("chat")
    setIsChatOpen(true)
    void sendChatMessage(quickChat)
  }

  const handleChatToggle = () => {
    setIsChatOpen((prev) => !prev)
    setActiveTab("chat")
    setQuickChats([...QUICK_CHAT_SUGGESTIONS])
  }

  const handleChatClose = () => {
    setIsChatOpen(false)
    setActiveTab("map")
    setQuickChats([...QUICK_CHAT_SUGGESTIONS])
  }

  const handleSetWorkplaceClick = () => {
    setWorkplaceInput(workplaceLocation?.name ?? "")
    setIsWorkplaceModalOpen(true)
  }

  const handleWorkplaceSubmit = (event: React.FormEvent) => {
    event.preventDefault()

    const placeName = workplaceInput.trim()
    if (!placeName) return

    setIsWorkplaceModalOpen(false)
    setWorkplaceInput("")
    void sendChatMessage(`My workplace is at ${placeName}`)
  }

  const handleClearWorkplace = () => {
    setWorkplaceLocation(null)
  }

  const handleSelectProperty = (prop: Property) => {
    setSelectedProperty(prop)
    setPreviewProperty(prop)
  }

  const handleViewOnMap = (prop: Property | null) => {
    if (!prop) return
    setSelectedProperty(prop)
    setActiveTab("map")
    setIsListingsOpen(true)
  }

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-[#0d3529] font-sans">
      {isWorkplaceModalOpen && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-[1.5rem] border border-[#d8d1c8] bg-[#f5f3ee] p-5 shadow-[0_25px_60px_rgba(12,53,41,0.28)]">
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[#5b6f68]">Workplace</p>
                <h3 className="text-xl font-semibold text-[#183c32]">Set your office</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsWorkplaceModalOpen(false)}
                className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-[#183c32] shadow-sm transition hover:bg-[#eef2ee]"
                aria-label="Close workplace modal"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleWorkplaceSubmit} className="space-y-4">
              <div>
                <label htmlFor="workplace-name" className="mb-1.5 block text-sm font-medium text-[#183c32]">
                  Workplace name or address
                </label>
                <input
                  id="workplace-name"
                  type="text"
                  value={workplaceInput}
                  onChange={(event) => setWorkplaceInput(event.target.value)}
                  placeholder="e.g. BGC Taguig, Makati CBD, Ayala Tower"
                  className="w-full rounded-xl border border-[#d8d1c8] bg-white px-3 py-2.5 text-sm text-[#183c32] placeholder:text-slate-400 focus:border-[#123f33] focus:outline-none focus:ring-2 focus:ring-[#123f33]/20"
                />
              </div>

              <div className="rounded-xl border border-[#d8d1c8] bg-[#f9f6f2] p-3 text-sm text-[#4d635d]">
                We’ll use this to help match properties based on commute time and location preference.
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsWorkplaceModalOpen(false)}
                  className="rounded-xl border border-[#d8d1c8] bg-white px-4 py-2 text-sm font-medium text-[#183c32] transition hover:bg-[#eef2ee]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!workplaceInput.trim()}
                  className="rounded-xl bg-[#0d3529] px-4 py-2 text-sm font-medium text-[#f3efe7] transition hover:bg-[#173f32] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Save Workplace
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <PropertyDetailModal
        property={previewProperty}
        workplaceLocation={workplaceLocation}
        onSetWorkplaceClick={handleSetWorkplaceClick}
        onClose={() => setPreviewProperty(null)}
        onViewOnMap={handleViewOnMap}
      />

      <div className="w-full shrink-0">
        <Header
          workplaceLocation={workplaceLocation}
          activeTab={activeTab}
          activePropertiesCount={activeProperties.length}
          onSetWorkplaceClick={handleSetWorkplaceClick}
          onClearWorkplace={handleClearWorkplace}
          onTabChange={setActiveTab}
        />
      </div>

      <div className="relative flex h-full min-h-0 w-full flex-1 overflow-hidden">
        <aside
          className={`flex h-full shrink-0 flex-col border-r border-[#d8d1c8] bg-[#f5f3ee] shadow-[8px_0_20px_rgba(12,53,41,0.18)] transition-all duration-300 ease-in-out ${
            isListingsOpen ? "w-full md:w-[340px] lg:w-[380px]" : "w-0 overflow-hidden border-r-0"
          }`}
        >
          {isListingsOpen && (
            <div className="flex h-full min-h-0 flex-col bg-[#f5f3ee]">
              <div className="flex items-center justify-between border-b border-[#d8d1c8] bg-[#0d3529] px-4 py-3 text-[#f3efe7]">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-400">Properties</p>
                  <h2 className="text-lg font-semibold text-white">Listings</h2>
                </div>
                <button
                  type="button"
                  onClick={() => setIsListingsOpen(false)}
                  className="inline-flex items-center gap-1 rounded-full border border-[#285744] bg-[#173f32] px-2.5 py-1.5 text-[11px] font-medium text-[#f3efe7] transition hover:bg-[#1d4d3f]"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                  Collapse
                </button>
              </div>
              <div className="border-b border-[#d8d1c8] bg-[#f9f6f2] p-3 space-y-3">
                <div className="flex items-center gap-2 rounded-xl border border-[#d8d1c8] bg-[#f0eee9] px-3 py-2 text-sm text-[#234b42] shadow-sm">
                  <Search className="h-4 w-4 text-slate-400" />
                  <input
                    type="text"
                    value={searchTerm}
                    onChange={(event) => {
                      const nextValue = event.target.value
                      setSearchTerm(nextValue)
                      void handleSearchProperties(nextValue)
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") void handleSearchProperties()
                    }}
                    placeholder="Search location or property name"
                    className="w-full border-0 bg-transparent text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => void handleSearchProperties()}
                    className="rounded-lg bg-[#0d3529] px-2.5 py-1.5 text-[11px] font-medium text-[#f3efe7] transition hover:bg-[#173f32]"
                  >
                    Search
                  </button>
                </div>

                <div className="flex items-center gap-1.5 overflow-x-auto rounded-full border border-[#d8d1c8] bg-[#f0eee9] p-1.5">
                  {LISTING_FILTERS.map((filter) => (
                    <button
                      key={filter}
                      type="button"
                      onClick={() => setActiveFilter(filter)}
                      className={`shrink-0 whitespace-nowrap rounded-full px-2.5 py-1.5 text-[11px] font-medium transition sm:text-xs ${
                        activeFilter === filter
                          ? "bg-[#0d3529] text-[#f3efe7] shadow-sm"
                          : "bg-transparent text-[#234b42] hover:bg-[#e7e3dc] hover:text-[#0d3529]"
                      }`}
                    >
                      {filter}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex-1 space-y-3 overflow-y-auto p-3">
                {!hasActiveProperties ? (
                  <div className="flex h-full min-h-[220px] flex-col items-center justify-center rounded-2xl border border-dashed border-[#c9c2b9] bg-[#f9f6f2] p-6 text-center">
                    <p className="text-base font-semibold text-[#183c32]">No properties yet</p>
                    <p className="mt-2 max-w-xs text-sm text-[#4d635d]">
                      Search by location or property name, or ask the assistant for recommendations.
                    </p>
                  </div>
                ) : hasPropertyResults ? (
                  filteredProperties.map((property) => {
                    const isSelected = selectedProperty?.listing_id === property.listing_id

                    return (
                      <div
                        key={property.listing_id}
                        className={`cursor-pointer rounded-2xl border bg-white p-3 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md ${
                          isSelected ? "border-[#214e40] ring-2 ring-[#d8ddd8]" : "border-[#d8d1c8]"
                        }`}
                        onClick={() => setSelectedProperty(property)}
                      >
                        <div className="mb-2 flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                            <Building2 className="h-3.5 w-3.5 text-[#123f33]" />
                            {property.category ?? "Property"}
                          </div>
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation()
                              setPreviewProperty(property)
                            }}
                            className="inline-flex items-center rounded-full bg-[#0d3529] px-2 py-1 text-[11px] font-medium text-[#f3efe7] transition hover:bg-[#173f32]"
                          >
                            View
                          </button>
                        </div>

                        <h3 className="text-base font-semibold leading-snug text-[#183c32]">{property.title}</h3>

                        <div className="mt-2 flex items-center gap-1.5 text-sm text-slate-600">
                          <MapPin className="h-3.5 w-3.5 text-slate-400" />
                          <span>{property.village_name}</span>
                        </div>

                        <div className="mt-3 flex items-center gap-4 text-sm text-slate-600">
                          <span className="inline-flex items-center gap-1">
                            <Bed className="h-3.5 w-3.5 text-slate-400" />
                            {property.num_bedrooms} bd
                          </span>
                          <span className="inline-flex items-center gap-1">
                            <Bath className="h-3.5 w-3.5 text-slate-400" />
                            {property.num_bathrooms} ba
                          </span>
                        </div>

                        <div className="mt-3 flex items-center justify-between">
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.16em] text-slate-400">Price</p>
                            <p className="text-lg font-bold text-[#123f33]">₱{property.price_total.toLocaleString()}</p>
                          </div>
                          {property.commute_info && (
                            <span className="rounded-full border border-slate-200 bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-600">
                              {property.commute_info.duration_mins} mins
                            </span>
                          )}
                        </div>
                      </div>
                    )
                  })
                ) : (
                  <div className="rounded-2xl border border-dashed border-[#c9c2b9] bg-[#f9f6f2] p-5 text-center text-sm text-[#4d635d]">
                    No properties match this filter.
                  </div>
                )}
              </div>
            </div>
          )}
        </aside>

        <main className="relative flex-1 overflow-hidden bg-[#0d3529]">
          {isMobileView ? (
            activeTab === "chat" ? (
              <div className="flex h-full flex-col bg-[#f5f3ee]">
                <div className="flex items-center justify-between border-b bg-[#0d3529] px-4 py-3 text-[#f3efe7]">
                  <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#d9d4cc]/20 text-[#d9d4cc]">
                      <Sparkles className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold">Property Assistant</p>
                      <p className="text-[10px] uppercase tracking-[0.18em] text-[#d9d4cc]">Online</p>
                    </div>
                  </div>
                </div>

                <div className="min-h-0 flex-1 overflow-hidden">
                  <ChatMessageList
                    messages={messages}
                    selectedProperty={selectedProperty}
                    isLoading={isLoading}
                    chatEndRef={chatEndRef}
                    onSelectProperty={handleSelectProperty}
                  />
                </div>

                <div className="border-t bg-white p-3">
                  <ChatInput
                    input={input}
                    isLoading={isLoading}
                    quickChats={quickChats}
                    onInputChange={setInput}
                    onSubmit={handleSendMessage}
                    onQuickChatSelect={handleQuickChatSelect}
                  />
                </div>
              </div>
            ) : (
              <div className="absolute inset-0">
                <div className="absolute inset-x-0 top-0 z-20 flex items-center justify-between gap-3 px-3 py-3 sm:px-4">
                  {!isListingsOpen && (
                    <button
                      type="button"
                      onClick={() => setIsListingsOpen(true)}
                      className="inline-flex items-center justify-center rounded-full border border-[#d8d1c8] bg-[#f5f3ee]/95 p-2.5 text-[#183c32] shadow-md backdrop-blur transition hover:bg-[#f9f6f2]"
                      aria-label="Open listings"
                    >
                      <span className="flex flex-col gap-1">
                        <span className="block h-0.5 w-5 rounded-full bg-current" />
                        <span className="block h-0.5 w-5 rounded-full bg-current" />
                        <span className="block h-0.5 w-5 rounded-full bg-current" />
                      </span>
                    </button>
                  )}
                </div>

                <div className="h-full w-full pt-16 sm:pt-16">
                  <div className="h-full w-full rounded-t-[1.3rem] border-t border-[#d8d1c8] bg-[#f5f3ee] p-2 shadow-[0_-10px_30px_rgba(12,53,41,0.12)] sm:p-3">
                    <PropertyMap
                      properties={filteredProperties}
                      selectedProperty={selectedProperty}
                      workplaceLocation={workplaceLocation}
                      onSelectProperty={handleSelectProperty}
                      onClearNearby={() => setSelectedProperty(null)}
                    />
                  </div>
                </div>
              </div>
            )
          ) : (
            <>
              <div className="absolute inset-0">
                <div className="absolute inset-x-0 top-0 z-20 flex items-center justify-between gap-3 px-3 py-3 sm:px-4">
                  {!isListingsOpen && (
                    <button
                      type="button"
                      onClick={() => setIsListingsOpen(true)}
                      className="inline-flex items-center justify-center rounded-full border border-[#d8d1c8] bg-[#f5f3ee]/95 p-2.5 text-[#183c32] shadow-md backdrop-blur transition hover:bg-[#f9f6f2]"
                      aria-label="Open listings"
                    >
                      <span className="flex flex-col gap-1">
                        <span className="block h-0.5 w-5 rounded-full bg-current" />
                        <span className="block h-0.5 w-5 rounded-full bg-current" />
                        <span className="block h-0.5 w-5 rounded-full bg-current" />
                      </span>
                    </button>
                  )}
                </div>

                <div className="h-full w-full pt-16 sm:pt-16">
                  <div className="h-full w-full rounded-t-[1.3rem] border-t border-[#d8d1c8] bg-[#f5f3ee] p-2 shadow-[0_-10px_30px_rgba(12,53,41,0.12)] sm:p-3">
                    <PropertyMap
                      properties={filteredProperties}
                      selectedProperty={selectedProperty}
                      workplaceLocation={workplaceLocation}
                      onSelectProperty={handleSelectProperty}
                      onClearNearby={() => setSelectedProperty(null)}
                    />
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={handleChatToggle}
                className="absolute bottom-5 right-5 z-40 inline-flex h-14 w-14 items-center justify-center rounded-full bg-[#0d3529] text-[#f3efe7] shadow-[0_12px_30px_rgba(12,53,41,0.35)] transition hover:-translate-y-1 hover:bg-[#173f32]"
                aria-label="Toggle assistant"
              >
                <MessageCircleMore className="h-6 w-6" />
              </button>

              {isChatOpen && (
                <div className="absolute bottom-24 right-5 z-50 flex h-[480px] w-[340px] flex-col overflow-hidden rounded-[1.5rem] border border-[#d8d1c8] bg-[#f5f3ee] shadow-[0_20px_45px_rgba(12,53,41,0.18)]">
                  <div className="flex items-center justify-between border-b bg-[#0d3529] px-4 py-3 text-[#f3efe7]">
                    <div className="flex items-center gap-2">
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#d9d4cc]/20 text-[#d9d4cc]">
                        <Sparkles className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold">Property Assistant</p>
                        <p className="text-[10px] uppercase tracking-[0.18em] text-[#d9d4cc]">Online</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={handleChatClose}
                      className="rounded-full bg-[#173f32] p-1.5 text-[#f3efe7] transition hover:bg-[#1d4d3f]"
                      aria-label="Close assistant"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>

                  <div className="min-h-0 flex-1 overflow-hidden">
                    <ChatMessageList
                      messages={messages}
                      selectedProperty={selectedProperty}
                      isLoading={isLoading}
                      chatEndRef={chatEndRef}
                      onSelectProperty={handleSelectProperty}
                    />
                  </div>

                  <div className="border-t bg-white p-3">
                    <ChatInput
                      input={input}
                      isLoading={isLoading}
                      quickChats={quickChats}
                      onInputChange={setInput}
                      onSubmit={handleSendMessage}
                      onQuickChatSelect={handleQuickChatSelect}
                    />
                  </div>
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  )
}