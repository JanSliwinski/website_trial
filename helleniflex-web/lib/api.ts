import type { BatteryConfig, BatteryPreset, OptimizeResult } from "./types";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function runOptimize(date: string, battery: BatteryConfig): Promise<OptimizeResult> {
  return apiFetch<OptimizeResult>("/api/optimize", {
    method: "POST",
    body: JSON.stringify({ date, battery }),
  });
}

export function fetchPresets(): Promise<BatteryPreset[]> {
  return apiFetch<BatteryPreset[]>("/api/battery-presets");
}
