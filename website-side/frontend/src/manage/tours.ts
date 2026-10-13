// Guided tours: what each Management page is for and how to use it.
// A step points at the element marked data-tour="<target>"; steps whose
// element isn't on screen (another role, phone vs. desktop, no data yet) are
// skipped. Text is English here and translated with t() when shown.
import type { StaffUser } from "./staffContext"
import { isManagement } from "./format"

export type TourStep = { target?: string; title: string; body: string }

const SYNC = "Sync pulls the latest records from the central database (Supabase) into ALTY. Only management roles see this button."

/** The parts most list pages share: header, summary tiles, search and table. */
function listPage(title: string, intro: string, extra: { actions?: string; tiles?: string; table?: string } = {}): TourStep[] {
  return [
    { target: "page-header", title, body: intro },
    { target: "tiles", title: "Summary at a glance", body: extra.tiles ?? "Totals for this page. Tiles that light up when you point at them are buttons: select one to filter the list, select it again to clear the filter." },
    { target: "filters", title: "Search and filter", body: "Type to search the list; the dropdowns next to it narrow it further. Results update as you type." },
    { target: "table", title: "Open a record", body: extra.table ?? "Select a row (or press Enter on it) to see everything about that record. Select a column heading to sort by it; select it again to reverse the order." },
    ...(extra.actions ? [{ target: "page-actions", title: "Actions", body: extra.actions }] : []),
  ]
}

export const TOURS: Record<string, (user: StaffUser | null) => TourStep[]> = {
  welcome: () => [
    { title: "Welcome to ALTY", body: "This short tour shows you around the Management System. Use Next and Back to move, or close it at any time — you can replay it from the Help button." },
    { target: "nav", title: "The main menu", body: "Every page you can open is listed here, in three groups: Main (day-to-day records), Intelligence (analysis) and Operations (documents, staff and settings). You only see the pages your role allows." },
    { target: "menu-button", title: "The main menu", body: "Open this to see every page you can open. You only see the pages your role allows." },
    { target: "bottom-nav", title: "Quick navigation", body: "Your most used pages and your profile, one tap away." },
    { target: "my-work", title: "My Work", body: "Your own clients, reservations, sales and client reviews, from the agent record linked to your account." },
    { target: "search", title: "Search everything", body: "Type at least 2 letters to find properties, clients, transactions, agents, documents and partners in one place." },
    { target: "bell", title: "Notifications", body: "Alerts about things that need you, such as a document that failed to process. The number shows how many you haven't read." },
    { target: "help", title: "Help is always here", body: "Open this to replay the tour of any page. You can also press the ? key. Look for the ? icons next to terms too: they explain what the term means." },
    { target: "profile", title: "Your account", body: "Your profile, photo and password. Sign out with the button beside it when you're done, especially on a shared computer." },
    { title: "You're all set", body: "Each page shows its own short tour the first time you open it. You can turn these off in the Help menu or in Settings." },
  ],

  "/manage": () => [
    { target: "dash-greeting", title: "Your dashboard", body: "A live summary of the whole business: properties, buyers and sellers, transactions, revenue, agents and documents." },
    { target: "dash-kpis", title: "Key numbers", body: "Each card shows one total with its breakdown underneath. “Documents needing attention” turns red when a document failed to process — open Document Repository to fix it." },
    { target: "dash-charts", title: "Trends over time", body: "Monthly transactions and revenue. The table button on a chart shows the same numbers as a table, which is easier to read with a screen reader." },
    { target: "dash-refresh", title: "Refresh", body: "Loads the latest numbers. The dashboard also refreshes each time you open it." },
  ],

  "/manage/properties": (user) => listPage("Properties", "Every property listing and where it stands: Available, Reserved or Sold. Reserved and Sold come from reservation and sale documents, so you never change them by hand.", { actions: isManagement(user?.role) ? SYNC : undefined }),

  "/manage/clients": (user) => listPage("Buyers & Sellers", "Everyone buying or selling with Abellar Realty. Clients are created automatically from buyer, reservation and sale documents and from website accounts — there's no “Add client” button.", { actions: isManagement(user?.role) ? SYNC : undefined }),

  "/manage/transactions": (user) => listPage("Transactions", "Every reservation and sale. Transactions come from processed documents and are never typed in by hand, so each one stays tied to the documents that prove it.", { actions: isManagement(user?.role) ? SYNC : undefined }),

  "/manage/agents": (user) => listPage("Agents", "Your agents and the work recorded for each one: clients, reservations, sales and verified client reviews.", { actions: isManagement(user?.role) ? SYNC : undefined }),

  "/manage/partners": () => listPage("Partners / Developers", "Developers and partner companies Abellar Realty works with. Active partners appear on the website's home page.", { actions: "Add a new partner here. To link a listing to its developer, open the listing on the Properties page." }),

  "/manage/analytics": () => [
    { target: "page-header", title: "Analytics", body: "How sales and listings are performing, computed from the recorded properties, transactions and agents. Below each chart, ALTY explains the results in plain words." },
    { target: "page-actions", title: "Choose the period", body: "Pick how many months the numbers cover." },
    { target: "tiles", title: "Summary at a glance", body: "The headline numbers for the chosen period. Point at the ? icons to see how each one is calculated." },
  ],

  "/manage/forecasting": () => [
    { target: "page-header", title: "Forecasting", body: "Projections for the coming months, based on the recorded monthly history. A forecast only appears when there is enough real history to make one — ALTY never invents numbers." },
    { target: "page-actions", title: "What to forecast", body: "Choose the measure to project and how many months ahead to look." },
  ],

  "/manage/insights": () => [
    { target: "page-header", title: "Recommendations", body: "Everything ALTY's analysis currently flags, highest priority first. Each item gives the finding, a suggested action, the data behind it and the rule used — the decision always stays with management." },
    { target: "tiles", title: "By priority", body: "Select a priority to show only those items; select it again to show everything." },
    { target: "page-actions", title: "Refresh", body: "Runs the analysis again on the latest records." },
  ],

  "/manage/media": () => [
    { target: "page-header", title: "Digital Preview", body: "Property photos and their automatic quality checks: resolution, sharpness, brightness and contrast. Only photos that pass are shown on the website." },
    { target: "tiles", title: "Summary at a glance", body: "How many photos there are and how many properties have them." },
    { target: "page-actions", title: "Upload photos", body: "Choose a property first, then upload its photos. Each photo is checked as soon as it arrives." },
  ],

  "/manage/documents": () => [
    { target: "page-header", title: "Document Repository", body: "Upload documents and ALTY handles them automatically: it reads, classifies and matches each one, then records the property, client, agent and transaction it describes." },
    { target: "page-actions", title: "Upload and organize", body: "Upload new documents and keep them tidy in folders." },
    { target: "tiles", title: "Processing status", body: "Select a tile to show only those documents. “Failed” documents show which stage went wrong and why, so they can be fixed and processed again." },
    { target: "filters", title: "Search and filter", body: "Find a document by name, client, property or reference, or narrow the list by folder, type and status." },
    { target: "table", title: "Open a document", body: "Select a row to see what ALTY extracted from the document, its history and the records it's linked to." },
  ],

  "/manage/workforce": () => [
    { target: "page-header", title: "Workforce", body: "Who is on the team, staff accounts by role, and how client work is shared across agents." },
    { target: "tiles", title: "Summary at a glance", body: "Totals for staff accounts and agents, and recent completed sales." },
    { target: "workforce-plan", title: "Demand vs capacity", body: "Expected deals next month divided by the deals one agent handles gives the agents needed, per branch. When a branch is short, ALTY suggests moving agents from a branch with spare capacity first, then recruiting. You can change the deals-per-agent figure and recalculate." },
  ],

  "/manage/branches": () => listPage("Branches", "Your offices side by side: agents, listings, revenue, commission, the month-to-month change, the trend and next month's forecast. A sale counts for its agent's branch.", {
    actions: "Add a branch here. Then give each agent a branch on the Agents page and each listing a branch on the Properties page.",
    table: "Select a branch to see its monthly revenue, forecast and agents. Sort by any column to rank the branches.",
  }),

  "/manage/recruitment": () => listPage("Recruitment", "Agent applicants from application to onboarding: Applied, Screening, Interview, Approved, then Onboarded. Onboarding creates the agent record with a branch and designation.", {
    actions: "Record a new applicant here.",
    table: "Select an applicant to move them to the next stage, reject them (with a reason), or onboard them once approved.",
  }),

  "/manage/users": (user) => listPage("Users & Access", "Staff accounts for the desktop app and this website — one account works in both. Each role opens only the pages it's allowed to.", {
    actions: user?.role === "Administrator" ? "Add a new staff account here." : undefined,
    table: user?.role === "Administrator" ? "Every staff account, its role and when it last signed in. Use the buttons at the end of a row to edit the account or reset its password." : "Every staff account, its role and when it last signed in. Select a column heading to sort by it.",
  }),

  "/manage/audit": () => listPage("Audit Logs", "A permanent record of every sign-in, record change, document action and sync, from both the desktop app and the website. Entries can't be edited or deleted.", {
    actions: "Export CSV downloads the log as a spreadsheet file.",
  }),

  "/manage/settings": () => [
    { target: "page-header", title: "Settings", body: "Change how ALTY looks for you." },
    { target: "settings-appearance", title: "Appearance", body: "Dark or light mode. The choice is saved on this browser." },
    { target: "settings-language", title: "Language", body: "Use the Management System in English or Filipino. Record details such as names and addresses stay as they were entered." },
    { target: "settings-help", title: "Tours and help", body: "Turn the automatic tours on or off, or start them all over again." },
  ],

  "/manage/profile": () => [
    { target: "page-header", title: "My profile", body: "Your account details, profile picture and password. Use a strong password that you don't use anywhere else." },
  ],

  "/manage/my-work": () => [
    { target: "page-header", title: "My Work", body: "Your own clients, open reservations, sales and client reviews, from the agent record linked to your account." },
    { target: "tiles", title: "Summary at a glance", body: "Your totals. These update when new documents about your clients are processed." },
  ],
}
