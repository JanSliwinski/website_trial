import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** 96 quarter-hour labels: "00:00" … "23:45" */
export const TIME_LABELS: string[] = Array.from({ length: 96 }, (_, i) => {
  const h = Math.floor(i / 4).toString().padStart(2, "0");
  const m = ((i % 4) * 15).toString().padStart(2, "0");
  return `${h}:${m}`;
});

/** 97 labels for SoC trajectory (adds "24:00") */
export const SOC_TIME_LABELS: string[] = [...TIME_LABELS, "24:00"];

export function fmtEur(v: number): string {
  return new Intl.NumberFormat("en-EU", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(v);
}

export function fmtPct(v: number | null): string {
  if (v === null) return "—";
  return v.toFixed(1) + "%";
}

/** Min date the optimizer supports (14+ days of synthetic history). */
export const DATE_MIN = "2024-01-20";
/** Max date covered by synthetic data. */
export const DATE_MAX = "2026-12-30";
