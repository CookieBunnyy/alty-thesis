import React from "react"
import { MessageSquare, Map as MapIcon } from "lucide-react"
import type { HeaderProps } from "../types"
import { SiteHeader } from "./SiteHeader"

/** Map page header: the site navigation, plus the existing mobile
 *  Chat Assistance / Interactive Map tabs underneath. */
export const Header: React.FC<HeaderProps> = ({ activeTab, activePropertiesCount, onTabChange }) => {
  return (
    <div>
      <SiteHeader />

      {/* Mobile/Tablet tab navigation (unchanged) */}
      <div className="flex border-b border-ab-border-strong bg-ab-bg/60 text-ab-text md:hidden">
        <button
          onClick={() => onTabChange("chat")}
          className={`flex flex-1 items-center justify-center space-x-2 py-2.5 text-xs font-semibold transition ${
            activeTab === "chat" ? "border-b-2 border-ab-border bg-ab-card-2 text-ab-text" : "text-ab-muted hover:text-ab-text"
          }`}
        >
          <MessageSquare className="h-4 w-4" />
          <span>Chat Assistance</span>
        </button>
        <button
          onClick={() => onTabChange("map")}
          className={`flex flex-1 items-center justify-center space-x-2 py-2.5 text-xs font-semibold transition ${
            activeTab === "map" ? "border-b-2 border-ab-border bg-ab-card-2 text-ab-text" : "text-ab-muted hover:text-ab-text"
          }`}
        >
          <MapIcon className="h-4 w-4" />
          <span>Interactive Map ({activePropertiesCount})</span>
        </button>
      </div>
    </div>
  )
}
