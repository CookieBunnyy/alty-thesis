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
  commute_info?: CommuteInfo; // 👈 Populated by backend OSRM calculations
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

export interface MapProps {
  properties: Property[];
  selectedProperty: Property | null;
  workplaceLocation?: LocationPoint | null;
  onSelectProperty: (property: Property) => void;
  onClearNearby?: () => void;
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
}

export interface HeaderProps {
  workplaceLocation: LocationPoint | null
  activeTab: "chat" | "map"
  activePropertiesCount: number
  onSetWorkplaceClick: () => void
  onClearWorkplace: () => void
  onTabChange: (tab: "chat" | "map") => void
}