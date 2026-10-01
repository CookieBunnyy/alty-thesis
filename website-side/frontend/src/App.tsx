import React, { useState, useRef, useEffect, useMemo } from "react"
import {
  Bath,
  Bed,
  Briefcase,
  Building2,
  ChevronDown,
  ChevronLeft,
  ChevronUp,
  CircleAlert,
  LoaderCircle,
  MapPin,
  MessageCircleMore,
  Search,
  Sparkles,
  X,
} from "lucide-react"
import { PropertyMap } from "./components/MapContainer"
import { PropertyDetailModal } from "./components/PropertyDetailModal"
import { Header } from "./components/Header"
import { ChatMessageList } from "./components/ChatMessageList"
import { ChatInput } from "./components/ChatInput"
import { WorkplaceDialog } from "./components/WorkplaceDialog"
import { SelectedPropertyPanel } from "./components/SelectedPropertyPanel"
import { ClientTransactionModal } from "./components/ClientTransactionModal"
import type { ChatMessage, Property, LocationPoint, PlaceResult, RouteSelection, TrafficStatus, TravelMode } from "./types"
import { API_URL, CHAT_API_URL, publicUrl } from "./config"
import { useTheme } from "./hooks/useTheme"
import { useAuth } from "./lib/auth"
import { navigate, useLocation } from "./lib/router"
import { SignInPrompt } from "./components/SignInPrompt"
import { RowSkeleton } from "./components/Skeleton"
import { useCommute } from "./hooks/useCommute"
import { formatKm, formatMinutes, getCapabilities, requestCurrentPosition, reversePlace, searchPlaces } from "./lib/mapApi"

// Live, AVAILABLE properties from the main Alty API (documents + central data).
const PROPERTIES_URL = `${API_URL}/api/v1/public/properties`
const LISTING_FILTERS = ["All", "Apartment", "Villa", "Duplex", "Warehouse"] as const
const QUICK_CHAT_SUGGESTIONS = [
  "Find a condo in BGC under 8k monthly",
  "Show me 3-bedroom houses in Alabang",
  "Properties near my office in Makati",
  "I want a duplex with a 2M down payment",
  "Apartment in Taguig within 30 minutes commute",
  "Affordable studio in Pasig",
] as const
const WORKPLACE_KEY = "alty-workplace"
// Preferred default mode when a commute loads: the first one the provider answered.
const MODE_PREFERENCE: TravelMode[] = ["driving", "motorcycle", "bicycle", "walking"]

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

const loadSavedWorkplace = (): LocationPoint | null => {
  try {
    const saved = JSON.parse(window.localStorage.getItem(WORKPLACE_KEY) ?? "null")
    return saved && Number.isFinite(saved.lat) && Number.isFinite(saved.lng) && saved.name ? saved : null
  } catch {
    return null
  }
}

export default function App() {
  const { theme } = useTheme()
  const { client } = useAuth()
  const { search } = useLocation()
  const [signInNext, setSignInNext] = useState<string | null>(null)
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
  // "loading" until the first response, so an empty list isn't mistaken for
  // "no properties" while the server is still answering.
  const [propertiesStatus, setPropertiesStatus] = useState<"loading" | "ready" | "error">("loading")
  const [isShowingRecommendations, setIsShowingRecommendations] = useState(false)
  const [selectedProperty, setSelectedProperty] = useState<Property | null>(null)
  const [workplaceLocation, setWorkplaceLocation] = useState<LocationPoint | null>(loadSavedWorkplace)
  const [activeTab, setActiveTab] = useState<"chat" | "map">("map")
  const [previewProperty, setPreviewProperty] = useState<Property | null>(null)
  const [isListingsOpen, setIsListingsOpen] = useState(() => (typeof window !== "undefined" ? window.innerWidth >= 768 : true))
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [isWorkplaceModalOpen, setIsWorkplaceModalOpen] = useState(false)
  const [quickChats, setQuickChats] = useState<string[]>([...QUICK_CHAT_SUGGESTIONS])
  const [activeFilter, setActiveFilter] = useState<ListingFilter>("All")
  const [searchTerm, setSearchTerm] = useState("")
  const [isMobileView, setIsMobileView] = useState(() => (typeof window !== "undefined" ? window.innerWidth < 768 : false))

  // Map state
  const [routeSelection, setRouteSelection] = useState<RouteSelection>({ mode: "driving", routeId: "A" })
  const [trafficAvailable, setTrafficAvailable] = useState(false)
  const [trafficMessage, setTrafficMessage] = useState("")
  const [trafficLegend, setTrafficLegend] = useState<TrafficStatus["legend"]>([])
  const [showTraffic, setShowTraffic] = useState(false)
  const [currentPosition, setCurrentPosition] = useState<{ lat: number; lng: number } | null>(null)
  const [isPickingLocation, setIsPickingLocation] = useState(false)
  const [focusPoint, setFocusPoint] = useState<{ lat: number; lng: number; zoom?: number } | null>(null)
  const [placeResults, setPlaceResults] = useState<PlaceResult[] | null>(null)
  const [isSearchingPlaces, setIsSearchingPlaces] = useState(false)
  const [notice, setNotice] = useState("")
  const [transaction, setTransaction] = useState<{ property: Property; type: "RESERVED" | "SOLD" } | null>(null)
  const [isSheetExpanded, setIsSheetExpanded] = useState(false)

  const chatEndRef = useRef<HTMLDivElement | null>(null)
  const commute = useCommute(workplaceLocation, selectedProperty)

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

  // The workplace is remembered on this device (no account needed).
  useEffect(() => {
    try {
      if (workplaceLocation) window.localStorage.setItem(WORKPLACE_KEY, JSON.stringify(workplaceLocation))
      else window.localStorage.removeItem(WORKPLACE_KEY)
    } catch {
      /* storage blocked: kept for this visit only */
    }
  }, [workplaceLocation])

  useEffect(() => {
    getCapabilities()
      .then((caps) => {
        setTrafficAvailable(caps.traffic.available)
        setTrafficMessage(caps.traffic.message)
        setTrafficLegend(caps.traffic.legend)
      })
      .catch(() => setTrafficMessage("Live traffic data is not available."))
  }, [])

  // Show the chosen travel mode if the provider routed it, otherwise the
  // first mode it could route (derived, so it follows each new commute).
  const commuteResult = commute.result
  const effectiveSelection = useMemo<RouteSelection>(() => {
    if (!commuteResult) return routeSelection
    const routed = (mode: TravelMode) => commuteResult.modes[mode]?.status === "ok"
    const mode = routed(routeSelection.mode) ? routeSelection.mode : MODE_PREFERENCE.find(routed) ?? routeSelection.mode
    const routes = commuteResult.modes[mode]?.routes ?? []
    const keepRoute = mode === routeSelection.mode && routes.some((route) => route.id === routeSelection.routeId)
    return { mode, routeId: keepRoute ? routeSelection.routeId : "A" }
  }, [commuteResult, routeSelection])

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(""), 6000)
    return () => window.clearTimeout(timer)
  }, [notice])

  const loadAvailableProperties = React.useCallback(() => {
    fetch(PROPERTIES_URL)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((data) => {
        if (Array.isArray(data)) {
          setActiveProperties(data)
          setIsShowingRecommendations(false)
        }
        setPropertiesStatus("ready")
      })
      .catch((err) => {
        console.error("Failed to load properties:", err)
        setPropertiesStatus((status) => (status === "ready" ? status : "error"))
      })
  }, [])

  const retryProperties = () => {
    setPropertiesStatus("loading")
    loadAvailableProperties()
  }

  useEffect(() => {
    loadAvailableProperties()
  }, [loadAvailableProperties])

  // Property names filter the list as you type; on submit the same query is
  // also looked up as a place (location or workplace).
  const handleSearchSubmit = async (overrideQuery?: string) => {
    const query = (overrideQuery ?? searchTerm).trim()
    if (query.length < 2) {
      setPlaceResults(null)
      return
    }
    setIsSearchingPlaces(true)
    try {
      setPlaceResults(await searchPlaces(query))
    } catch (error) {
      setPlaceResults(null)
      setNotice((error as Error).message)
    } finally {
      setIsSearchingPlaces(false)
    }
  }

  // `workplace` overrides the saved one for this request (used right after
  // Set Workplace, before the new state has rendered).
  const sendChatMessage = async (textMessage: string, workplaceOverride?: LocationPoint) => {
    if (!textMessage.trim() || isLoading) return
    const workplace = workplaceOverride ?? workplaceLocation

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
      const response = await fetch(`${CHAT_API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage.text,
          workplace_lat: workplace?.lat || null,
          workplace_lng: workplace?.lng || null,
          workplace_name: workplace?.name || null,
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

      if (data.recommendations?.length > 0) {
        setActiveProperties(data.recommendations)
        setIsShowingRecommendations(true)
      }
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
    setIsPickingLocation(false)
    setIsWorkplaceModalOpen(true)
  }

  const saveWorkplace = (place: LocationPoint) => {
    setWorkplaceLocation(place)
    setIsWorkplaceModalOpen(false)
    setIsPickingLocation(false)
    setPlaceResults(null)
    if (!selectedProperty) setFocusPoint({ lat: place.lat, lng: place.lng, zoom: 14 })
    // As before the redesign: ask the assistant for the listings with the best
    // commute to the new workplace. The exact coordinates are sent, and the
    // wording avoids "near / work at / office in", which the chat service
    // would otherwise treat as a place name to look up again.
    void sendChatMessage("Show properties with the shortest commute to my workplace.", place)
  }

  const handleClearWorkplace = () => {
    setWorkplaceLocation(null)
    setIsWorkplaceModalOpen(false)
  }

  const handlePickLocation = async (point: { lat: number; lng: number }) => {
    const place = await reversePlace(point.lat, point.lng).catch(() => null)
    saveWorkplace({ ...point, name: place?.name || `Pinned location (${point.lat.toFixed(4)}, ${point.lng.toFixed(4)})` })
  }

  const handleLocate = async () => {
    try {
      const position = await requestCurrentPosition()
      setCurrentPosition(position)
      setFocusPoint({ ...position, zoom: 15 })
      setActiveTab("map")
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  const handleToggleTraffic = () => {
    if (!trafficAvailable) {
      setShowTraffic(false)
      setNotice(trafficMessage || "Live traffic data is not available.")
      return
    }
    setShowTraffic((value) => !value)
  }

  // Chat recommendations: select and open the full details (unchanged flow).
  const handleSelectProperty = (prop: Property) => {
    setSelectedProperty(prop)
    setPreviewProperty(prop)
  }

  // Map pins and list cards: select, show commute + actions in the panel/sheet.
  const selectOnMap = (prop: Property) => {
    setSelectedProperty(prop)
    setRouteSelection((current) => ({ ...current, routeId: "A" }))
    setFocusPoint(null)
    setIsSheetExpanded(false)
    setActiveTab("map")
    setIsListingsOpen(!isMobileView) // desktop: details in the side panel; mobile: bottom sheet
  }

  const handleViewOnMap = (prop: Property | null) => {
    if (!prop) return
    selectOnMap(prop)
  }

  const clearSelection = () => {
    setSelectedProperty(null)
    setIsSheetExpanded(false)
  }

  const activeMode = commute.result?.modes[effectiveSelection.mode]
  const activeRoute = activeMode?.routes.find((route) => route.id === effectiveSelection.routeId) ?? activeMode?.routes[0]

  // Reserve / Purchase need a signed-in client; otherwise ask them to sign
  // in and come back to this property with the same action.
  const requestTransaction = (property: Property, type: "RESERVED" | "SOLD") => {
    if (client) {
      setTransaction({ property, type })
      return
    }
    setPreviewProperty(null)
    setSignInNext(`/map?property=${encodeURIComponent(String(property.listing_id))}&action=${type}`)
  }

  // Deep link: /map?property=ID[&action=RESERVED|SOLD] (e.g. after sign-in).
  const linkedPropertyId = search.get("property")
  const linkedAction = search.get("action")
  useEffect(() => {
    if (!linkedPropertyId || activeProperties.length === 0) return
    // Syncing from the URL (an external system): runs once per link.
    /* eslint-disable react-hooks/set-state-in-effect */
    const property = activeProperties.find((item) => String(item.listing_id) === linkedPropertyId)
    if (property) {
      selectOnMap(property)
      if ((linkedAction === "RESERVED" || linkedAction === "SOLD") && client) {
        setTransaction({ property, type: linkedAction })
      }
    } else {
      setNotice("That property is no longer available.")
    }
    /* eslint-enable react-hooks/set-state-in-effect */
    navigate("/map", { replace: true })
    // selectOnMap is recreated each render; the link is consumed once
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [linkedPropertyId, linkedAction, activeProperties, client])

  // Leave room for the mobile bottom sheet when fitting routes.
  const mapBottomInset = isMobileView && selectedProperty && !isSheetExpanded ? 150 : 0
  const mapStatus =
    propertiesStatus === "loading" && !hasActiveProperties ? (
      <div className="pointer-events-none absolute inset-x-0 bottom-6 z-[1040] flex justify-center px-4">
        <p role="status" className="flex items-center gap-2.5 rounded-full border border-ab-border bg-ab-card/95 px-4 py-2 text-sm font-semibold text-ab-text shadow-lg backdrop-blur">
          <span className="ab-spinner h-4 w-4" aria-hidden="true" /> Loading properties…
        </p>
      </div>
    ) : propertiesStatus === "error" && !hasActiveProperties ? (
      <div className="absolute inset-x-0 bottom-6 z-[1040] flex justify-center px-4">
        <p role="alert" className="flex items-center gap-3 rounded-full border border-ab-danger/40 bg-ab-card px-4 py-2 text-sm text-ab-text shadow-lg">
          Unable to load properties.
          <button type="button" onClick={retryProperties} className="font-semibold text-ab-accent hover:underline">Try again</button>
        </p>
      </div>
    ) : null

  const mapView = (
    <PropertyMap
      properties={filteredProperties}
      selectedProperty={selectedProperty}
      workplaceLocation={workplaceLocation}
      onSelectProperty={selectOnMap}
      onClearNearby={clearSelection}
      theme={theme}
      commute={commute.result}
      routeSelection={effectiveSelection}
      onSelectRoute={(routeId) => setRouteSelection({ mode: effectiveSelection.mode, routeId })}
      showTraffic={showTraffic}
      trafficAvailable={trafficAvailable}
      trafficLegend={trafficLegend}
      onToggleTraffic={handleToggleTraffic}
      currentPosition={currentPosition}
      onLocate={handleLocate}
      isPickingLocation={isPickingLocation}
      onPickLocation={handlePickLocation}
      focusPoint={focusPoint}
      bottomInset={mapBottomInset}
      controlsTop={isMobileView ? 76 : 12}
    />
  )

  const selectedPanel = selectedProperty && (
    <SelectedPropertyPanel
      property={selectedProperty}
      workplace={workplaceLocation}
      routeSelection={effectiveSelection}
      onRouteSelectionChange={setRouteSelection}
      onSetWorkplaceClick={handleSetWorkplaceClick}
      onViewRoute={isMobileView ? () => setIsSheetExpanded(false) : undefined}
      onOpenDetails={() => setPreviewProperty(selectedProperty)}
      onTransaction={(type) => requestTransaction(selectedProperty, type)}
      onClose={clearSelection}
      compact={isMobileView}
      commute={commute}
    />
  )

  // Search box + prominent Set Workplace control, shared by desktop and mobile.
  const mapSearchBar = (
    <div className="relative w-full">
      <div className="flex items-center gap-2">
        <form
          role="search"
          onSubmit={(event) => {
            event.preventDefault()
            void handleSearchSubmit()
          }}
          className="flex min-h-12 min-w-0 flex-1 items-center gap-2 rounded-2xl border border-ab-border bg-ab-card px-3 shadow-md focus-within:border-ab-accent"
        >
          <Search className="h-4 w-4 shrink-0 text-ab-faint" />
          <label htmlFor="map-search" className="sr-only">
            Search properties or places
          </label>
          <input
            id="map-search"
            type="search"
            value={searchTerm}
            onChange={(event) => {
              setSearchTerm(event.target.value)
              if (!event.target.value.trim()) setPlaceResults(null)
            }}
            placeholder="Search property, area or place"
            className="min-w-0 flex-1 bg-transparent text-sm text-ab-text placeholder:text-ab-faint focus:outline-none"
          />
          {isSearchingPlaces ? (
            <LoaderCircle className="h-4 w-4 shrink-0 animate-spin text-ab-accent" />
          ) : (
            <button
              type="submit"
              disabled={searchTerm.trim().length < 2}
              className="hidden shrink-0 rounded-lg bg-ab-accent px-2.5 py-1.5 text-[11px] font-semibold text-ab-ink transition hover:bg-ab-accent-hover disabled:opacity-40 sm:block"
            >
              Search
            </button>
          )}
        </form>
        <button
          type="button"
          onClick={handleSetWorkplaceClick}
          title={workplaceLocation ? `Workplace: ${workplaceLocation.name}` : "Set your workplace to see commute routes"}
          className={`flex min-h-10 shrink-0 items-center gap-2 rounded-2xl px-3 text-sm font-semibold shadow-md transition sm:px-3.5 ${
            workplaceLocation
              ? "border border-ab-border bg-ab-card text-ab-text hover:bg-ab-hover"
              : "bg-ab-accent text-ab-ink hover:bg-ab-accent-hover"
          }`}
        >
          <Briefcase className={`h-4 w-4 shrink-0 ${workplaceLocation ? "text-ab-accent" : ""}`} />
          <span className="max-w-[84px] truncate sm:max-w-[150px]">
            {workplaceLocation ? workplaceLocation.name : isMobileView ? "Set Work" : "Set Workplace"}
          </span>
        </button>
      </div>

      {placeResults && (
        <div className="absolute inset-x-0 top-[calc(100%+6px)] z-[1100] max-h-72 overflow-y-auto rounded-2xl border border-ab-border bg-ab-card p-2 shadow-xl">
          <div className="flex items-center justify-between px-2 pb-1">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-ab-faint">Places</p>
            <button type="button" onClick={() => setPlaceResults(null)} aria-label="Close place results" className="p-1 text-ab-muted">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          {placeResults.length === 0 && <p className="px-2 py-2 text-sm text-ab-muted">No places matched “{searchTerm}”.</p>}
          {placeResults.map((place) => (
            <div key={`${place.lat},${place.lng}`} className="flex items-center gap-2 rounded-xl px-2 py-2 hover:bg-ab-hover">
              <MapPin className="h-4 w-4 shrink-0 text-ab-accent" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-ab-text">{place.name}</p>
                <p className="truncate text-xs text-ab-muted">{place.address}</p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setFocusPoint({ lat: place.lat, lng: place.lng, zoom: 15 })
                  setPlaceResults(null)
                  setActiveTab("map")
                  if (isMobileView) setIsListingsOpen(false)
                }}
                className="min-h-9 shrink-0 rounded-lg border border-ab-border px-2.5 text-xs font-semibold text-ab-text hover:bg-ab-card-2"
              >
                Show
              </button>
              <button
                type="button"
                onClick={() => saveWorkplace({ lat: place.lat, lng: place.lng, name: place.name })}
                className="min-h-9 shrink-0 rounded-lg bg-ab-accent-soft px-2.5 text-xs font-semibold text-ab-accent"
              >
                Set as work
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )

  const listingsButton = !isListingsOpen && (
    <button
      type="button"
      onClick={() => setIsListingsOpen(true)}
      className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-ab-border bg-ab-card text-ab-text shadow-md transition hover:bg-ab-hover"
      aria-label="Open listings"
    >
      <span className="flex flex-col gap-1">
        <span className="block h-0.5 w-5 rounded-full bg-current" />
        <span className="block h-0.5 w-5 rounded-full bg-current" />
        <span className="block h-0.5 w-5 rounded-full bg-current" />
      </span>
    </button>
  )

  const noticeToast = notice && (
    <div role="status" className="pointer-events-auto absolute inset-x-3 bottom-4 z-[1200] mx-auto flex max-w-md items-start gap-2 rounded-xl border border-ab-warning/40 bg-ab-card p-3 text-sm text-ab-text shadow-xl">
      <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-ab-warning" />
      <p className="flex-1">{notice}</p>
      <button type="button" onClick={() => setNotice("")} aria-label="Dismiss" className="text-ab-muted">
        <X className="h-4 w-4" />
      </button>
    </div>
  )

  return (
    <div className="flex h-dvh w-screen flex-col overflow-hidden bg-ab-sidebar font-sans">
      {isWorkplaceModalOpen && (
        <WorkplaceDialog
          current={workplaceLocation}
          onSave={saveWorkplace}
          onClear={handleClearWorkplace}
          onClose={() => setIsWorkplaceModalOpen(false)}
          onPickOnMap={() => {
            setIsWorkplaceModalOpen(false)
            setIsPickingLocation(true)
            setActiveTab("map")
            if (isMobileView) {
              setIsListingsOpen(false)
              clearSelection()
            }
          }}
        />
      )}

      <PropertyDetailModal
        property={previewProperty}
        workplaceLocation={workplaceLocation}
        onSetWorkplaceClick={handleSetWorkplaceClick}
        onClose={() => setPreviewProperty(null)}
        onViewOnMap={handleViewOnMap}
        onRequestTransaction={(property, type) => requestTransaction(property, type)}
        onTransactionSubmitted={() => {
          // The property is no longer AVAILABLE: refresh map and listings.
          setSelectedProperty(null)
          loadAvailableProperties()
        }}
      />

      {signInNext && <SignInPrompt next={signInNext} onClose={() => setSignInNext(null)} />}

      {transaction && (
        <ClientTransactionModal
          property={transaction.property}
          initialType={transaction.type}
          onClose={() => setTransaction(null)}
          onSubmitted={() => {
            setSelectedProperty(null)
            loadAvailableProperties()
          }}
        />
      )}

      <div className="w-full shrink-0">
        <Header
          activeTab={activeTab}
          activePropertiesCount={activeProperties.length}
          onTabChange={setActiveTab}
        />
      </div>

      <div className="relative flex h-full min-h-0 w-full flex-1 overflow-hidden">
        <aside
          className={`flex h-full shrink-0 flex-col border-r border-ab-border bg-ab-card shadow-[8px_0_20px_rgba(12,53,41,0.12)] transition-all duration-300 ease-in-out ${
            isListingsOpen ? "w-full md:w-[360px] lg:w-[400px]" : "w-0 overflow-hidden border-r-0"
          }`}
        >
          {isListingsOpen && !isMobileView && selectedProperty ? (
            <div className="flex h-full min-h-0 flex-col bg-ab-card">
              <div className="flex items-center justify-between border-b border-ab-border bg-ab-sidebar px-4 py-3">
                <button
                  type="button"
                  onClick={clearSelection}
                  className="inline-flex min-h-9 items-center gap-1 rounded-full border border-ab-border-strong bg-ab-card-2 px-3 text-xs font-medium text-ab-text transition hover:bg-ab-hover"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                  Back to results ({filteredProperties.length})
                </button>
                <button
                  type="button"
                  onClick={() => setIsListingsOpen(false)}
                  className="rounded-full p-2 text-ab-muted transition hover:bg-ab-hover"
                  aria-label="Collapse panel"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto p-4">{selectedPanel}</div>
            </div>
          ) : (
            isListingsOpen && (
              <div className="flex h-full min-h-0 flex-col bg-ab-card">
                <div className="flex items-center justify-between border-b border-ab-border bg-ab-sidebar px-4 py-3 text-ab-text">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ab-faint">Properties</p>
                    <h2 className="text-lg font-semibold text-ab-text">
                      Listings <span className="text-sm font-medium text-ab-muted">({filteredProperties.length})</span>
                    </h2>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsListingsOpen(false)}
                    className="inline-flex min-h-9 items-center gap-1 rounded-full border border-ab-border-strong bg-ab-card-2 px-3 py-1.5 text-[11px] font-medium text-ab-text transition hover:bg-ab-hover"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                    {isMobileView ? "Map" : "Collapse"}
                  </button>
                </div>
                <div className="space-y-3 border-b border-ab-border bg-ab-card p-3">
                  {isMobileView && mapSearchBar}

                  <div className="flex items-center gap-1.5 overflow-x-auto rounded-full border border-ab-border bg-ab-input p-1.5">
                    {LISTING_FILTERS.map((filter) => (
                      <button
                        key={filter}
                        type="button"
                        onClick={() => setActiveFilter(filter)}
                        className={`min-h-8 shrink-0 whitespace-nowrap rounded-full px-3 py-1.5 text-[11px] font-medium transition sm:text-xs ${
                          activeFilter === filter
                            ? "bg-ab-accent text-ab-ink shadow-sm"
                            : "bg-transparent text-ab-muted hover:bg-ab-hover hover:text-ab-text"
                        }`}
                      >
                        {filter}
                      </button>
                    ))}
                  </div>

                  {isShowingRecommendations && (
                    <div className="flex items-center justify-between gap-2 rounded-xl bg-ab-accent-soft px-3 py-2 text-xs text-ab-text">
                      <span className="flex items-center gap-1.5">
                        <Sparkles className="h-3.5 w-3.5 text-ab-accent" /> Showing assistant recommendations
                      </span>
                      <button type="button" onClick={loadAvailableProperties} className="font-semibold text-ab-accent hover:underline">
                        Show all
                      </button>
                    </div>
                  )}
                </div>

                <div className="flex-1 space-y-3 overflow-y-auto p-3">
                  {propertiesStatus === "loading" && !hasActiveProperties ? (
                    <div role="status" className="space-y-3">
                      <span className="sr-only">Loading properties…</span>
                      <RowSkeleton />
                      <RowSkeleton />
                      <RowSkeleton />
                      <RowSkeleton />
                    </div>
                  ) : propertiesStatus === "error" && !hasActiveProperties ? (
                    <div role="alert" className="flex min-h-[220px] flex-col items-center justify-center rounded-2xl border border-ab-danger/40 bg-ab-danger/10 p-6 text-center">
                      <p className="text-base font-semibold text-ab-text">Unable to load properties</p>
                      <p className="mt-2 max-w-xs text-sm text-ab-muted">The server didn't respond. Check your connection and try again.</p>
                      <button type="button" onClick={retryProperties} className="mt-4 rounded-xl bg-ab-accent px-4 py-2 text-sm font-semibold text-ab-ink">
                        Try again
                      </button>
                    </div>
                  ) : !hasActiveProperties ? (
                    <div className="flex h-full min-h-[220px] flex-col items-center justify-center rounded-2xl border border-dashed border-ab-border bg-ab-card p-6 text-center">
                      <p className="text-base font-semibold text-ab-text">No properties yet</p>
                      <p className="mt-2 max-w-xs text-sm text-ab-muted">
                        Search by location or property name, or ask the assistant for recommendations.
                      </p>
                    </div>
                  ) : hasPropertyResults ? (
                    filteredProperties.map((property) => {
                      const isSelected = selectedProperty?.listing_id === property.listing_id
                      const cover = property.photos?.[0] ?? (property.media?.[0] ? publicUrl(property.media[0]) : null)

                      return (
                        <div
                          key={property.listing_id}
                          role="button"
                          tabIndex={0}
                          className={`cursor-pointer rounded-2xl border bg-ab-card-2 p-3 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md focus-visible:outline-2 focus-visible:outline-ab-accent ${
                            isSelected ? "border-ab-accent ring-2 ring-ab-accent/30" : "border-ab-border"
                          }`}
                          onClick={() => selectOnMap(property)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault()
                              selectOnMap(property)
                            }
                          }}
                        >
                          <div className="flex gap-3">
                            {cover && <img src={cover} alt="" className="h-20 w-20 shrink-0 rounded-xl object-cover" />}
                            <div className="min-w-0 flex-1">
                              <div className="mb-1 flex items-center justify-between gap-2">
                                <div className="flex min-w-0 items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-ab-muted">
                                  <Building2 className="h-3.5 w-3.5 shrink-0 text-ab-text" />
                                  <span className="truncate">{property.category ?? "Property"}</span>
                                </div>
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation()
                                    setPreviewProperty(property)
                                  }}
                                  className="inline-flex min-h-8 shrink-0 items-center rounded-full bg-ab-accent px-2.5 text-[11px] font-medium text-ab-ink transition hover:bg-ab-accent-hover"
                                >
                                  View
                                </button>
                              </div>

                              <h3 className="text-base font-semibold leading-snug text-ab-text">{property.title}</h3>

                              <div className="mt-1 flex items-center gap-1.5 text-sm text-ab-muted">
                                <MapPin className="h-3.5 w-3.5 shrink-0 text-ab-faint" />
                                <span className="truncate">{property.village_name}</span>
                              </div>
                            </div>
                          </div>

                          <div className="mt-3 flex items-end justify-between">
                            <div>
                              <p className="text-[10px] uppercase tracking-[0.16em] text-ab-faint">Price</p>
                              <p className="text-lg font-bold text-ab-accent">₱{property.price_total.toLocaleString()}</p>
                            </div>
                            <div className="flex items-center gap-3 text-sm text-ab-muted">
                              <span className="inline-flex items-center gap-1">
                                <Bed className="h-3.5 w-3.5 text-ab-faint" />
                                {property.num_bedrooms} bd
                              </span>
                              <span className="inline-flex items-center gap-1">
                                <Bath className="h-3.5 w-3.5 text-ab-faint" />
                                {property.num_bathrooms} ba
                              </span>
                            </div>
                          </div>
                          {property.commute_info && (
                            <p className="mt-2 text-[11px] text-ab-muted">
                              By car to {workplaceLocation?.name ?? "workplace"}: {property.commute_info.distance_km} km ·{" "}
                              {property.commute_info.duration_mins} min (road route)
                            </p>
                          )}
                        </div>
                      )
                    })
                  ) : (
                    <div className="rounded-2xl border border-dashed border-ab-border bg-ab-card p-5 text-center text-sm text-ab-muted">
                      No properties match this filter.
                    </div>
                  )}
                </div>
              </div>
            )
          )}
        </aside>

        <main className="relative flex-1 overflow-hidden bg-ab-sidebar">
          {isMobileView ? (
            activeTab === "chat" ? (
              <div className="flex h-full flex-col bg-ab-card">
                <div className="flex items-center justify-between border-b bg-ab-sidebar px-4 py-3 text-ab-text">
                  <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-ab-accent-soft text-ab-muted">
                      <Sparkles className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold">Property Assistant</p>
                      <p className="text-[10px] uppercase tracking-[0.18em] text-ab-muted">Online</p>
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

                <div className="border-t bg-ab-card-2 p-3">
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
                {/* Mobile: search + Set Work float over the full-screen map */}
                {!isListingsOpen && (
                  <div className="absolute inset-x-0 top-0 z-[1050] flex items-start gap-2 p-4">
                    {listingsButton}
                    <div className="min-w-0 flex-1">{mapSearchBar}</div>
                  </div>
                )}

                <div className="h-full w-full">{mapView}</div>
                {mapStatus}

                {selectedProperty && (
                  <div
                    className={`ab-sheet absolute inset-x-0 bottom-0 z-[1060] flex flex-col overflow-hidden rounded-t-[1.5rem] border-t border-ab-border bg-ab-card shadow-[0_-12px_30px_rgba(0,0,0,0.25)] ${
                      isSheetExpanded ? "max-h-[78%]" : "max-h-[150px]"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => setIsSheetExpanded((value) => !value)}
                      aria-expanded={isSheetExpanded}
                      className="flex w-full shrink-0 flex-col items-center gap-1 px-4 pb-2 pt-2 text-left"
                    >
                      <span className="h-1 w-10 rounded-full bg-ab-border-strong" />
                      <span className="flex w-full items-center gap-3">
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-base font-semibold text-ab-text">{selectedProperty.title}</span>
                          <span className="block text-sm font-bold text-ab-accent">
                            ₱{Number(selectedProperty.price_total).toLocaleString()}
                          </span>
                          <span className="block truncate text-xs text-ab-muted">
                            {!workplaceLocation
                              ? "Set your workplace to see commute times"
                              : commute.isLoading
                                ? "Calculating road routes…"
                                : activeRoute
                                  ? `${activeMode?.label}: ${formatKm(activeRoute.distance_m)} · ${formatMinutes(activeRoute.duration_s)} from work${
                                      activeRoute.traffic && activeRoute.traffic.delay_s >= 60
                                        ? ` (+${formatMinutes(activeRoute.traffic.delay_s)} traffic)`
                                        : ""
                                    }`
                                  : commute.error ?? "Route information is currently unavailable."}
                          </span>
                        </span>
                        {isSheetExpanded ? (
                          <ChevronDown className="h-5 w-5 shrink-0 text-ab-muted" />
                        ) : (
                          <ChevronUp className="h-5 w-5 shrink-0 text-ab-muted" />
                        )}
                      </span>
                    </button>
                    {isSheetExpanded && <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-6">{selectedPanel}</div>}
                  </div>
                )}
                {noticeToast}
              </div>
            )
          ) : (
            <>
              <div className="absolute inset-0 flex flex-col">
                {/* Desktop: search / location / Set Workplace over the map */}
                <div className="absolute inset-x-3 top-3 z-[1050] flex items-start gap-2 p-4 pr-16">
                  {listingsButton}
                  <div className="w-full max-w-2xl">{mapSearchBar}</div>
                </div>

                <div className="h-full w-full p-2 sm:p-3">
                  <div className="h-full w-full overflow-hidden rounded-[1.3rem] border border-ab-border bg-ab-card shadow-[0_-10px_30px_rgba(12,53,41,0.12)]">
                    {mapView}
                  </div>
                  {mapStatus}
                </div>
              </div>
              {noticeToast}

              <button
                type="button"
                onClick={handleChatToggle}
                className="absolute bottom-5 right-5 z-[1100] inline-flex h-14 w-14 items-center justify-center rounded-full bg-ab-accent text-ab-ink shadow-[0_12px_30px_rgba(12,53,41,0.35)] transition hover:-translate-y-1 hover:bg-ab-accent-hover"
                aria-label="Toggle assistant"
              >
                <MessageCircleMore className="h-6 w-6" />
              </button>

              {isChatOpen && (
                <div className="absolute bottom-24 right-5 z-[1100] flex h-[480px] w-[340px] flex-col overflow-hidden rounded-[1.5rem] border border-ab-border bg-ab-card shadow-[0_20px_45px_rgba(12,53,41,0.18)]">
                  <div className="flex items-center justify-between border-b bg-ab-sidebar px-4 py-3 text-ab-text">
                    <div className="flex items-center gap-2">
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-ab-accent-soft text-ab-muted">
                        <Sparkles className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold">Property Assistant</p>
                        <p className="text-[10px] uppercase tracking-[0.18em] text-ab-muted">Online</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={handleChatClose}
                      className="rounded-full bg-ab-card-2 p-1.5 text-ab-text transition hover:bg-ab-hover"
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

                  <div className="border-t bg-ab-card-2 p-3">
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
