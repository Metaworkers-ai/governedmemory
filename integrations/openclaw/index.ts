/**
 * Governed Memory — OpenClaw plugin (v1)
 * ------------------------------------------------------------------------
 * Wraps an OpenClaw agent with GovernedMemory's trust governance by calling the
 * GovernedMemory REST API (github.com/Metaworkers-ai/governedmemory). No changes to
 * the GovernedMemory core — this plugin just `fetch`es its endpoints.
 *
 * Three lifecycle hooks:
 *   1. message_received    -> write inbound *channel* content to GovernedMemory, which
 *                             injection-scores it and labels it trusted/untrusted/
 *                             quarantined ("govern on write"). Channel-only: it does
 *                             not fire on `openclaw agent` turns (hook 2 covers those).
 *   2. before_prompt_build -> score the incoming turn through the Write Governor; if it
 *                             comes back injection-flagged / quarantined, mark the turn
 *                             poisoned. This is where flagging happens for agent turns.
 *                             (Governed retrieval of trusted-only memory is wired on the
 *                             client but not yet injected into the prompt — v1 scope.)
 *   3. before_tool_call    -> if the current turn is flagged and the tool is sensitive,
 *                             return { block: true } so the action never fires
 *                             ("privilege gate blocks it") — the enforcement point.
 *
 * Config comes from plugins.entries.governed-memory.config (see openclaw.plugin.json).
 *
 * Hook payloads confirmed against a live OpenClaw gateway: the incoming user text is in
 * `ctx.prompt` (before_prompt_build) and the tool name is `ctx.toolName`
 * (before_tool_call). `message_received` is channel-only and its payload shape is
 * best-effort (it is not exercised by `openclaw agent` turns).
 */

import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

type Taint = "trusted" | "untrusted" | "quarantined";

interface GovConfig {
  apiUrl: string;
  apiKey: string;
  customerId?: string;
  inboundSourceType?: string;
  sensitiveTools?: string[];
  injectionThreshold?: number;
}

interface WriteResult {
  id: string;
  taint: Taint;
  injectionScore: number;
}

// --- minimal GovernedMemory REST client (Node 24 has global fetch; no SDK needed) ---
class GovernedMemoryClient {
  constructor(private readonly baseUrl: string, private readonly apiKey: string) {}

  private async request(path: string, body: unknown): Promise<any> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      throw new Error(`GovernedMemory ${path} -> ${res.status}: ${await res.text()}`);
    }
    return res.json();
  }

  /** Write content through the Write Governor; returns its trust label + injection score. */
  async write(p: {
    customerId: string;
    agentId: string;
    sessionId: string;
    content: string;
    sourceType: string;
    sourceRef: string;
  }): Promise<WriteResult> {
    // Body mirrors api/schemas.py::WriteBody (tenant is resolved from the API key).
    const rec = await this.request("/v1/memory", {
      customer_id: p.customerId,
      agent_id: p.agentId,
      session_id: p.sessionId,
      content: p.content,
      provenance: { source_type: p.sourceType, source_ref: p.sourceRef, confidence: 0.9 },
    });
    return {
      id: rec.id,
      taint: (rec.trust?.taint ?? "untrusted") as Taint,
      injectionScore: Number(rec.trust?.injection_score ?? 0),
    };
  }

  /** Governed retrieval — trusted memory only (untrusted/quarantined excluded). */
  async retrieve(p: { query: string; agentId: string; sessionId: string; k?: number }): Promise<any[]> {
    // Body mirrors api/schemas.py::RetrieveBody.
    return this.request("/v1/retrieve", {
      query: p.query,
      agent_id: p.agentId,
      session_id: p.sessionId,
      k: p.k ?? 10,
      include_untrusted: false,
    });
  }
}

export default definePluginEntry({
  id: "governed-memory",
  name: "Governed Memory",
  description:
    "Injection-scores memory on write, governs retrieval, and blocks tool calls backed by poisoned memory.",
  register(api) {
    const cfg = (api.pluginConfig ?? {}) as GovConfig;
    const log = (api as any).log ?? console;

    if (!cfg.apiUrl || !cfg.apiKey) {
      log.error?.("[governed-memory] missing apiUrl/apiKey in config — plugin is inert.");
      return;
    }

    const gm = new GovernedMemoryClient(cfg.apiUrl, cfg.apiKey);
    const customerId = cfg.customerId ?? "openclaw-agent";
    const inboundSourceType = cfg.inboundSourceType ?? "untrusted_web";
    const injectionThreshold = cfg.injectionThreshold ?? 0.7;
    const sensitiveTools = new Set(
      cfg.sensitiveTools ?? [
        "web_fetch",
        "send_money",
        "send_email",
        "http_request",
        "shell",
        "payment",
        "wire_transfer",
      ],
    );

    // Turn-scoped poison flag. On OpenClaw agent turns, before_prompt_build fires
    // once (with the incoming prompt) and before_tool_call fires for each tool, in
    // that order within the same turn — so a flag set at prompt-build gates the tool
    // calls in that turn. (Demo-scoped; a production build keys this per run/session.)
    let turnPoisoned: { reason: string } | null = null;

    // 1) GOVERN ON WRITE ---------------------------------------------------------
    api.on("message_received", async (ctx: any) => {
      // Channel-only hook (not fired on `openclaw agent` turns). The payload shape
      // varies by channel, so fall back through the likely field names.
      const sessionId = String(ctx?.threadId ?? ctx?.sessionId ?? "default");
      const content = String(ctx?.text ?? ctx?.message?.text ?? ctx?.content ?? "");
      if (!content) return;
      try {
        const r = await gm.write({
          customerId,
          agentId: "openclaw",
          sessionId,
          content,
          sourceType: inboundSourceType,
          sourceRef: `openclaw:${sessionId}`,
        });
        const poisoned = r.taint === "quarantined" || r.injectionScore >= injectionThreshold;
        if (poisoned) {
          log.warn?.(
            `[governed-memory] inbound channel content is ${r.taint}, injection ${r.injectionScore.toFixed(2)}`,
          );
        }
      } catch (err) {
        log.error?.(`[governed-memory] write failed: ${String(err)}`);
      }
      // observe-only: no decision returned, message flows on normally.
    });

    // 2) GOVERNED RETRIEVAL ------------------------------------------------------
    api.on("before_prompt_build", async (ctx: any) => {
      // Confirmed on a live box: the incoming user text is in ctx.prompt.
      turnPoisoned = null; // reset per turn
      const prompt = String(ctx?.prompt ?? "");
      if (!prompt) return;
      try {
        // Run the incoming turn through the Write Governor (injection scoring).
        const r = await gm.write({
          customerId,
          agentId: "openclaw",
          sessionId: "turn",
          content: prompt,
          sourceType: inboundSourceType,
          sourceRef: "openclaw:turn",
        });
        const flagged = r.taint === "quarantined" || r.injectionScore >= injectionThreshold;
        log.info?.(
          `[governed-memory] turn scored: taint ${r.taint}, injection ${r.injectionScore.toFixed(2)}, flagged ${flagged}`,
        );
        if (flagged) {
          turnPoisoned = { reason: `${r.taint}, injection ${r.injectionScore.toFixed(2)}` };
        }
      } catch (err) {
        log.error?.(`[governed-memory] turn scoring failed: ${String(err)}`);
      }
    });

    // 3) PRIVILEGE GATE — the enforcement point ---------------------------------
    api.on("before_tool_call", async (ctx: any) => {
      // Confirmed on a live box: the tool name is ctx.toolName.
      const toolName = String(ctx?.toolName ?? ctx?.tool ?? ctx?.name ?? "");
      if (!sensitiveTools.has(toolName)) return { block: false }; // only gate sensitive tools
      if (turnPoisoned) {
        const reason = `Blocked by Governed Memory: "${toolName}" was driven by a turn flagged ${turnPoisoned.reason} — the action is not backed by trusted memory.`;
        log.warn?.(`[governed-memory] ${reason}`);
        return { block: true, reason };
      }
      return { block: false };
    });

    log.info?.(
      "[governed-memory] registered: message_received, before_prompt_build, before_tool_call",
    );
  },
});
