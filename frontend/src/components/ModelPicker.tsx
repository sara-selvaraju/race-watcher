"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type AdminOverviewOut, type AgentOut, type ModelOptionOut } from "@/lib/api/client";

type Choice = NonNullable<AgentOut["model_choice"]>;

/** An agent's model on the admin page: what it is, what it costs, and a picker to change it. */
export function ModelPicker({ agent, choice, token }: { agent: AgentOut; choice: Choice; token: string }) {
  const [editing, setEditing] = useState(false);
  const chosenHere = choice.changed_at != null;

  return (
    <div>
      <dt className="text-ink-3">Model</dt>
      <dd>
        <code className="font-semibold break-all">{choice.id}</code>
        {choice.info && <span className="text-ink-3"> ({price(choice.info)})</span>}
        <span className="block text-ink-3">
          {chosenHere ? (
            <>
              Chosen here {when(choice.changed_at!)}. Default: <code>{choice.default}</code>
            </>
          ) : (
            <>
              Default, from <code>{choice.setting}</code>
            </>
          )}
        </span>
        {!editing && (
          <button type="button" className="mt-1 font-semibold text-turf underline" onClick={() => setEditing(true)}>
            Change model
          </button>
        )}
        {editing && <Editor agent={agent} choice={choice} token={token} onDone={() => setEditing(false)} />}
      </dd>
    </div>
  );
}

export function useModels(token: string) {
  return useQuery<ModelOptionOut[]>({
    queryKey: ["admin-models", token],
    staleTime: 60 * 60_000,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/models", { headers: { "X-Admin-Token": token } });
      if (error || !data) throw new Error("Couldn't fetch OpenRouter's model list");
      return data;
    },
  });
}

function Editor({ agent, choice, token, onDone }: { agent: AgentOut; choice: Choice; token: string; onDone: () => void }) {
  const qc = useQueryClient();
  const { data: models, error: modelsError } = useModels(token);
  const byId = new Map((models ?? []).map((m) => [m.id, m]));
  const options = [...new Set([choice.default, ...choice.suggested])];
  const [picked, setPicked] = useState(options.includes(choice.id) ? choice.id : "other");
  const [other, setOther] = useState(options.includes(choice.id) ? "" : choice.id);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listId = `models-${agent.key}`;

  async function save(model: string | null) {
    setSaving(true);
    setError(null);
    const { data, error: err } = await api.PUT("/api/v1/admin/agents/{key}/model", {
      params: { path: { key: agent.key } },
      body: { model },
      headers: { "X-Admin-Token": token },
    });
    setSaving(false);
    if (err || !data) {
      const detail = (err as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "Couldn't save the model");
      return;
    }
    qc.setQueryData<AdminOverviewOut>(["admin-overview", token], data);
    onDone();
  }

  const target = picked === "other" ? other.trim() : picked;

  return (
    <form
      className="mt-2 space-y-2 rounded-md border border-line bg-surface p-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (target) void save(target);
      }}
    >
      <fieldset className="space-y-1">
        <legend className="sr-only">Model for the {agent.name.toLowerCase()}</legend>
        {options.map((id) => {
          const info = byId.get(id);
          return (
            <label key={id} className="flex items-baseline gap-2">
              <input type="radio" name={listId} checked={picked === id} onChange={() => setPicked(id)} />
              <span className="min-w-0">
                <code className="break-all">{id}</code>
                {id === choice.default && <span className="text-ink-3"> (default)</span>}
                {info && <span className="block text-ink-3">{price(info)}</span>}
              </span>
            </label>
          );
        })}
        <label className="flex items-baseline gap-2">
          <input type="radio" name={listId} checked={picked === "other"} onChange={() => setPicked("other")} />
          <span>Another OpenRouter model</span>
        </label>
        {picked === "other" && (
          <>
            <input
              list={listId + "-list"}
              value={other}
              onChange={(e) => setOther(e.target.value)}
              placeholder="e.g. openai/gpt-5-mini"
              autoFocus
              className="w-full rounded-md border border-line bg-surface px-2 py-1"
            />
            <datalist id={listId + "-list"}>
              {(models ?? [])
                .filter((m) => !choice.needs_tools || m.tools)
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
            </datalist>
            {byId.get(other.trim()) && <p className="text-ink-3">{price(byId.get(other.trim())!)}</p>}
          </>
        )}
      </fieldset>

      {choice.needs_tools && <p className="text-ink-3">This agent needs a model that supports tool calling.</p>}
      {modelsError && <p className="text-ink-3">Prices unavailable: couldn&apos;t reach OpenRouter.</p>}
      <p className="text-ink-3">Used from the agent&apos;s next run. OpenRouter bills each run at the model&apos;s price.</p>
      {error && <p className="text-drift">{error}</p>}

      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" className="btn btn-primary" disabled={saving || !target || target === choice.id}>
          {saving ? "Saving…" : "Save model"}
        </button>
        <button type="button" className="underline text-ink-3" onClick={onDone}>
          Cancel
        </button>
        {choice.changed_at && (
          <button type="button" className="underline text-ink-3 ml-auto" onClick={() => void save(null)}>
            Go back to the default
          </button>
        )}
      </div>
    </form>
  );
}

function money(perM: string | null): string | null {
  if (perM == null) return null;
  const n = Number(perM);
  return n === 0 ? "free" : `$${n < 0.1 ? n.toFixed(3) : n < 10 ? n.toFixed(2) : n.toFixed(0)}`;
}

export function price(m: ModelOptionOut): string {
  const input = money(m.input_per_m);
  const output = money(m.output_per_m);
  if (!input || !output) return "price unknown";
  return `${input} in, ${output} out per million tokens`;
}

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-AU", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}
