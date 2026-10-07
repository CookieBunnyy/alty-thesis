import type { CallLabels } from "@/components/CallButton"
import { t } from "./i18n"

/** The call/QR dialog's text in the management system's language. */
export function callLabels(): CallLabels {
  return {
    title: t("Call {name}"),
    textTitle: t("Text {name}"),
    scan: t("Scan this with your phone's camera. Your phone app opens with the number filled in."),
    orCall: t("Open on this device"),
    copy: t("Copy number"),
    copied: t("Copied"),
    close: t("Close"),
  }
}
