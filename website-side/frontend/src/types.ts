export interface NearbyEstablishmentItem {
  name: string;
  distance_km: number;
  lat?: number | null;
  lng?: number | null;
}

export interface NearbyEstablishmentsMap {
  [category: string]: NearbyEstablishmentItem[];
}

export interface CommuteInfo {
  distance_km: number;
  duration_mins: number;
  convenience_score: 'Excellent' | 'Good' | 'Moderate' | 'Far';
}

export interface LocationPoint {
  lat: number;
  lng: number;
  name: string;
}

export interface Property {
  listing_id: number | string;
  listing_code?: string | null;
  status?: 'AVAILABLE' | 'RESERVED' | 'SOLD';
  media?: string[];
  title: string;
  category?: string;
  price_total: number;
  initial_dp?: number | null;
  monthly_rate?: number | null;
  num_bedrooms: number;
  num_bathrooms: number;
  has_balcony?: boolean;
  has_kitchen?: boolean;
  has_backyard?: boolean;
  has_garage?: boolean;
  garage_spaces?: number;
  layout_type?: string;
  village_name: string;
  lat: number | null;
  lng: number | null;
  photos?: string[];
  amenity_list?: any;
  nearby_establishments?: any;
  details?: string;
  commute_info?: CommuteInfo; // set by the chat service (OSRM driving route) for recommendations
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp?: string;
  status?: 'rejected' | 'clarification_needed' | 'success' | 'casual_chat' | 'no_match' | 'recommendation_found';
  recommendations?: Property[];
}

export interface CommuteAnalysis {
  distanceKm: number;
  durationMins: number;
  bestRouteName: string;
  timeSavingsScore: 'Excellent' | 'Good' | 'Moderate' | 'Far';
}

export type TravelMode = 'walking' | 'bicycle' | 'motorcycle' | 'driving';

export type RouteTag = 'shortest_distance' | 'shortest_time' | 'alternative';

export type TrafficLevel = 'slow' | 'moderate' | 'heavy' | 'closed';

export interface TrafficSegment {
  start: number; // index into RouteOption.geometry
  end: number;
  level: TrafficLevel;
  category: string; // JAM | ROAD_WORK | ROAD_CLOSURE | OTHER
  delay_s: number;
  speed_kmh: number | null;
}

/** Live traffic applied to a route by the provider (car / motorcycle only). */
export interface RouteTraffic {
  live: boolean;
  delay_s: number; // extra time caused by current traffic
  free_flow_duration_s: number | null; // same route with empty roads
  typical_duration_s: number | null; // historic traffic at this time
  congested_length_m: number | null;
  departure_time: string | null;
  segments: TrafficSegment[];
}

export interface RouteOption {
  id: string;
  distance_m: number; // road-network distance from the routing provider
  duration_s: number; // provider travel time (includes live traffic when `traffic` is set)
  geometry: [number, number][]; // [lat, lng] points along the road network
  summary: string;
  tags: RouteTag[];
  traffic?: RouteTraffic | null;
}

export interface ModeResult {
  label: string;
  status: 'ok' | 'unsupported' | 'no_route' | 'timeout' | 'rate_limited' | 'unavailable' | 'invalid';
  message: string | null;
  routes: RouteOption[];
}

export interface TrafficStatus {
  available: boolean;
  provider: string | null;
  message: string;
  legend: { level: string; label: string; color: string }[];
  attribution: string;
}

export interface CommuteResult {
  provider: string;
  attribution: string;
  straight_line_m: number; // geographic distance — never a travel distance
  live_traffic: boolean;
  modes: Record<TravelMode, ModeResult>;
  traffic: TrafficStatus;
}

export interface MapCapabilities {
  routing: {
    provider: string;
    available: boolean;
    attribution: string;
    alternatives: boolean;
    live_traffic: boolean;
    modes: Record<TravelMode, { label: string; supported: boolean }>;
  };
  traffic: TrafficStatus;
}

export interface PlaceResult {
  name: string;
  address: string;
  lat: number;
  lng: number;
}

export interface NearbyAgent {
  agent_id: string;
  full_name: string;
  agent_location: string | null;
  phone_number: string | null;
  client_rating: number | null; // average of client reviews
  review_count: number;
  star_rating: number | null; // legacy/system rating (not client reviews)
  completed_sales: number;
  straight_line_km: number | null;
  road_distance_km: number | null;
  travel_time_min: number | null;
}

export interface NearbyAgentsResult {
  property_id: number;
  property_status: string;
  ranking: string;
  routing: { available: boolean; mode: string; provider?: string; live_traffic?: boolean; message: string };
  agents: NearbyAgent[];
}

export interface RouteSelection {
  mode: TravelMode;
  routeId: string;
}

export interface MapProps {
  properties: Property[];
  selectedProperty: Property | null;
  workplaceLocation?: LocationPoint | null;
  onSelectProperty: (property: Property) => void;
  onClearNearby?: () => void;
  theme: 'dark' | 'light';
  commute?: CommuteResult | null;
  routeSelection?: RouteSelection;
  onSelectRoute?: (routeId: string) => void;
  showTraffic?: boolean;
  trafficAvailable?: boolean;
  trafficLegend?: TrafficStatus['legend'];
  onToggleTraffic?: () => void;
  currentPosition?: { lat: number; lng: number } | null;
  onLocate?: () => void;
  isPickingLocation?: boolean;
  onPickLocation?: (point: { lat: number; lng: number }) => void;
  focusPoint?: { lat: number; lng: number; zoom?: number } | null;
  bottomInset?: number;
  controlsTop?: number; // px from the top, to clear an overlaid search bar
}

export interface PropertyDetailModalProps {
  property: Property | null;
  workplaceLocation?: LocationPoint | null;
  onSetWorkplaceClick: () => void;
  onClose: () => void;
}

export interface CommuteCardProps {
  property: Property;
  workplace?: LocationPoint | null;
  onSetWorkplaceClick: () => void;
  routeSelection?: RouteSelection;
  onRouteSelectionChange?: (selection: RouteSelection) => void;
  onViewRoute?: () => void;
  // Shared state from the page, so the map and the panel refresh together.
  commute?: import('./hooks/useCommute').CommuteState;
}

export interface HeaderProps {
  activeTab: "chat" | "map"
  activePropertiesCount: number
  onTabChange: (tab: "chat" | "map") => void
}

// ---- Client accounts, reviews and the home page ----------------------------

export interface ClientProfile {
  full_name: string;
  email: string | null;
  phone_number: string | null;
  location: string | null;
  member_since: string;
}

export interface PublicAgent {
  agent_id: string;
  full_name: string;
  agent_location: string | null;
  phone_number: string | null;
  status: string | null;
  client_rating: number | null;
  review_count: number;
  star_rating: number | null;
}

/** A client review as anyone may see it: no contact details or client ID. */
export interface PublicReview {
  id: number;
  rating: number;
  review: string | null;
  reviewer: string; // "First L."
  verified: boolean;
  transaction_type: 'RESERVED' | 'SOLD' | null;
  created_at: string;
  updated_at: string;
  agent?: { agent_id: string; full_name: string | null };
  transaction_id?: string;
}

export interface AgentProfile extends PublicAgent {
  completed_sales: number;
  reviews: PublicReview[];
}

export interface HomeData {
  stats: {
    available_properties: number;
    active_agents: number;
    client_reviews: { average: number | null; count: number };
  };
  featured_properties: Property[];
  categories: { category: string; count: number }[];
  agents: PublicAgent[];
  reviews: PublicReview[];
}

export interface ClientTransaction {
  transaction_id: string;
  transaction_type: 'RESERVED' | 'SOLD';
  status: 'RESERVED' | 'COMPLETED' | 'CANCELLED';
  transaction_date: string;
  amount: number;
  property: { listing_id: number; title: string; village_name: string | null; status: string; photo: string | null };
  agent: {
    agent_id: string;
    full_name: string;
    phone_number: string | null;
    agent_location: string | null;
    client_rating: number | null;
    review_count: number;
  };
  review: { id: number; rating: number; review: string | null; updated_at: string } | null;
  can_review: boolean;
}
