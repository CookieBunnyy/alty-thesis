// Plain-language explanations of the terms used across the Management pages.
// Summary tiles, table columns, section titles and detail labels with one of
// these names get a "?" beside them that shows the explanation. English here;
// translated with t() when shown.
const TERMS: Record<string, string> = {
  // Sales and transactions
  "Open reservations": "Reservations that haven't become a completed sale or been cancelled yet.",
  "Completed sales": "Transactions that ended in a completed sale.",
  "Completed": "Transactions that ended in a completed sale.",
  "Reserved": "A buyer has reserved the property, usually with a reservation fee. It isn't sold yet.",
  "Reservations": "A reservation holds a property for a buyer before the sale is completed.",
  "Cancelled": "Reservations or sales that were called off.",
  "Sales value": "The total price of all completed sales.",
  "Sales revenue": "The total amount from completed sales in the period shown.",
  "Total amount": "The combined amount of the transactions shown.",
  "Average sale": "Sales revenue divided by the number of completed sales.",
  "Absorption rate": "The share of listings that are already sold — a sign of how quickly properties are being taken up.",
  "Recorded commission": "Commission amounts written on the processed transaction documents.",
  "Sales (90 days)": "Sales completed in the last 90 days, as recorded in ALTY.",

  // Agents
  "Performance": "Completed sales as a percentage of all the agent's recorded deals (reservations and sales).",
  "Client rating": "The average star rating from verified client reviews.",
  "Client-reviewed agents": "Agents who have at least one verified client review.",
  "Assigned clients": "Clients whose records name this agent.",

  // Records and sync
  "Sync": "Whether this record has been sent to the central database (Supabase). Pending records are sent on the next sync.",
  "Monthly": "The monthly payment or rate for this listing, when it has one.",
  "Latest": "The most recent transaction for this client, and its date.",
  "Related to": "The client and property this document is about.",
  "Details missing": "Partners whose type (for example, Developer) hasn't been set yet.",
  "With listings": "Partners that have at least one property listing linked to them.",

  // Documents
  "Processing": "ALTY is still reading and classifying these documents.",
  "Processed": "Documents ALTY has read and recorded successfully.",
  "Failed": "Documents that couldn't be processed. Open one to see the stage and the reason, then fix it and process it again.",
  "Archived": "Documents kept for the record but hidden from the everyday list.",
  "Documents needing attention": "Documents that failed, are still processing or are waiting their turn.",
  "Extracted information": "The details ALTY read from the document, such as names, prices and dates.",
  "Versions & audit trail": "Every version of this document and every action taken on it.",

  // Recommendations
  "High priority": "Problems that may cost sales or need action soon.",
  "Needs attention": "Things worth checking before they become problems.",
  "Positive": "Good results worth keeping up.",
  "For information": "Useful observations; no action needed.",

  // Staff and audit
  "Staff accounts": "People who can sign in to the desktop app and the Management System.",
  "Signed in (30 days)": "Accounts that signed in at least once in the last 30 days.",
  "Role": "Decides which pages and actions an account can use.",
  "Actor": "The staff account that performed the action.",
  "Record": "The record the action changed, such as a property or a document.",
  "Result": "Whether the action succeeded or failed.",
  "Linked agent record": "Connects a staff account to an agent record, so the person's My Work page shows that agent's clients and sales.",
  "Synchronization with the central database (Supabase)": "ALTY keeps its own records and sends new or changed ones to the shared central database used by the website.",
}

export function glossary(term: string): string | undefined {
  return TERMS[term]
}
