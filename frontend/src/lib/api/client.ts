import createClient from "openapi-fetch";
import { API_BASE_URL } from "@/lib/env";
import type { paths } from "./schema";

export const api = createClient<paths>({ baseUrl: API_BASE_URL });

export type MeetingOut = paths["/api/v1/meeting/today"]["get"]["responses"]["200"]["content"]["application/json"];
export type AlertsOut = paths["/api/v1/alerts"]["get"]["responses"]["200"]["content"]["application/json"];
export type StatusOut = paths["/api/v1/status"]["get"]["responses"]["200"]["content"]["application/json"];
