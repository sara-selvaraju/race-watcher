import createClient from "openapi-fetch";
import { API_BASE_URL } from "@/lib/env";
import type { paths } from "./schema";

export const api = createClient<paths>({ baseUrl: API_BASE_URL });

export type MeetingsOut = paths["/api/v1/meetings/today"]["get"]["responses"]["200"]["content"]["application/json"];
export type MeetingOut = MeetingsOut[number];
export type AlertsOut = paths["/api/v1/alerts"]["get"]["responses"]["200"]["content"]["application/json"];
export type StatusOut = paths["/api/v1/status"]["get"]["responses"]["200"]["content"]["application/json"];
