import React from "react"
import { Navigation, MessageSquare, Map as MapIcon, X } from "lucide-react"
import type { HeaderProps } from "../types"

export const Header: React.FC<HeaderProps> = ({
  workplaceLocation,
  activeTab,
  activePropertiesCount,
  onSetWorkplaceClick,
  onClearWorkplace,
  onTabChange,
}) => {
  return (
    <div>
      {/* Mobile/Tablet Header & Tab Navigation */}
      <div className="flex flex-col border-b bg-ab-sidebar text-ab-text md:hidden">
        <header className="flex items-center justify-between p-3">
          <div className="flex items-center space-x-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-ab-accent text-base font-black text-ab-ink">A</span>
            <div className="leading-tight">
              <h1 className="text-base font-extrabold tracking-wide text-ab-text">ALTY</h1>
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-ab-faint">Abellar Realty</p>
            </div>
          </div>
          <div className="flex items-center space-x-1">
            <button
              onClick={onSetWorkplaceClick}
              className="flex items-center space-x-1 rounded-md border border-ab-border-strong bg-ab-card-2 px-2.5 py-1 text-xs text-ab-muted"
            >
              <Navigation className="h-3 w-3" />
              <span>{workplaceLocation ? workplaceLocation.name : "Set Work"}</span>
            </button>
            {workplaceLocation && (
              <button
                onClick={onClearWorkplace}
                aria-label="Clear workplace"
                className="flex items-center justify-center rounded-md border border-ab-border-strong bg-ab-card-2 p-1.5 text-ab-muted hover:text-ab-danger"
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </div>
        </header>

        <div className="flex border-t border-ab-border-strong bg-ab-bg/60">
          <button
            onClick={() => onTabChange("chat")}
            className={`flex flex-1 items-center justify-center space-x-2 py-2.5 text-xs font-semibold transition ${
              activeTab === "chat"
                ? "border-b-2 border-ab-border bg-ab-card-2 text-ab-text"
                : "text-ab-muted hover:text-ab-text"
            }`}
          >
            <MessageSquare className="h-4 w-4" />
            <span>Chat Assistance</span>
          </button>
          <button
            onClick={() => onTabChange("map")}
            className={`flex flex-1 items-center justify-center space-x-2 py-2.5 text-xs font-semibold transition ${
              activeTab === "map"
                ? "border-b-2 border-ab-border bg-ab-card-2 text-ab-text"
                : "text-ab-muted hover:text-ab-text"
            }`}
          >
            <MapIcon className="h-4 w-4" />
            <span>Interactive Map ({activePropertiesCount})</span>
          </button>
        </div>
      </div>

      {/* Desktop Header */}
      <header className="hidden items-center justify-between border-b bg-ab-sidebar p-4 text-ab-text md:flex">
        <div className="flex items-center space-x-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-ab-accent text-base font-black text-ab-ink">A</span>
          <div className="leading-tight">
            <h1 className="text-lg font-extrabold tracking-wide text-ab-text">ALTY</h1>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-ab-faint">Abellar Realty · Property Finder</p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={onSetWorkplaceClick}
            className="flex items-center space-x-1.5 rounded-lg border border-ab-border-strong bg-ab-card-2 px-3 py-1.5 text-xs font-medium text-ab-muted transition hover:bg-ab-hover"
          >
            <Navigation className="h-3.5 w-3.5" />
            <span className="max-w-[120px] truncate">
              {workplaceLocation ? workplaceLocation.name : "Set Workplace"}
            </span>
          </button>
          {workplaceLocation && (
            <button
              onClick={onClearWorkplace}
              aria-label="Clear workplace"
              className="flex items-center justify-center rounded-lg border border-ab-border-strong bg-ab-card-2 p-1.5 text-ab-muted transition hover:bg-ab-hover hover:text-ab-danger"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </header>
    </div>
  )
}