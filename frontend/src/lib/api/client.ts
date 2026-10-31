import createClient from "openapi-fetch";
import { API_BASE_URL } from "@/lib/env";
import type { paths } from "./schema";

export const api = createClient<paths>({ baseUrl: API_BASE_URL });

export type MeetingsOut = paths["/api/v1/meetings"]["get"]["responses"]["200"]["content"]["application/json"];
export type MeetingOut = MeetingsOut[number];
export type AlertsOut = paths["/api/v1/alerts"]["get"]["responses"]["200"]["content"]["application/json"];
export type StatusOut = paths["/api/v1/status"]["get"]["responses"]["200"]["content"]["application/json"];
export type AdminOverviewOut =
  paths["/api/v1/admin/overview"]["get"]["responses"]["200"]["content"]["application/json"];
export type AgentOut = AdminOverviewOut["agents"][number];
export type ModelOptionOut =
  paths["/api/v1/admin/models"]["get"]["responses"]["200"]["content"]["application/json"][number];
export type PlaygroundOut =
  paths["/api/v1/admin/playground"]["post"]["responses"]["200"]["content"]["application/json"];
