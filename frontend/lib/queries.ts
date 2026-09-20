"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type {
  Coverage,
  FindingDetail,
  FindingList,
  History,
  Identity,
  Overview,
  Plan,
  ScanList,
  Script,
  SettingsData,
} from "./types";
export const keys = {
  identity: ["identity"],
  overview: ["overview"],
  history: ["history"],
  coverage: ["coverage"],
  findings: (q: string) => ["findings", q],
  finding: (id: string) => ["finding", id],
  plan: (id: string) => ["plan", id],
  script: (id: string) => ["script", id],
  scans: ["scans"],
  settings: ["settings"],
};
export const useIdentity = () =>
  useQuery({ queryKey: keys.identity, queryFn: () => api<Identity>("/api/identity") });
export const useOverview = () =>
  useQuery({ queryKey: keys.overview, queryFn: () => api<Overview>("/api/overview") });
export const useHistory = () =>
  useQuery({ queryKey: keys.history, queryFn: () => api<History>("/api/history") });
export const useCoverage = () =>
  useQuery({ queryKey: keys.coverage, queryFn: () => api<Coverage>("/api/coverage") });
export const useFindings = (q: string) =>
  useQuery({ queryKey: keys.findings(q), queryFn: () => api<FindingList>(`/api/findings?${q}`) });
export const useFinding = (id: string) =>
  useQuery({
    queryKey: keys.finding(id),
    queryFn: () => api<FindingDetail>(`/api/findings/${id}`),
    enabled: !!id,
  });
export const usePlan = (id: string) =>
  useQuery({
    queryKey: keys.plan(id),
    queryFn: () => api<Plan>(`/api/findings/${id}/plan`),
    enabled: !!id,
  });
export const useScript = (id: string) =>
  useQuery({
    queryKey: keys.script(id),
    queryFn: () => api<Script>(`/api/findings/${id}/script`),
    enabled: !!id,
  });
export const useScans = () =>
  useQuery({ queryKey: keys.scans, queryFn: () => api<ScanList>("/api/scans") });
export const useSettings = () =>
  useQuery({ queryKey: keys.settings, queryFn: () => api<SettingsData>("/api/settings") });
