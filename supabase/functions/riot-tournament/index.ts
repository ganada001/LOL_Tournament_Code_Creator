const TOURNAMENT_ROUTING_VALUES = new Set([
  "americas",
  "asia",
  "europe",
  "sea",
]);
const MAP_TYPES = new Set(["SUMMONERS_RIFT", "HOWLING_ABYSS"]);
const PICK_TYPES = new Set([
  "BLIND_PICK",
  "DRAFT_MODE",
  "ALL_RANDOM",
  "TOURNAMENT_DRAFT",
]);
const SPECTATOR_TYPES = new Set(["NONE", "LOBBYONLY", "ALL"]);
const RETRYABLE_STATUS_CODES = new Set([429, 500, 502, 503, 504]);
const CALLBACK_METADATA_LABEL_LIMIT = 120;

type RequestBody = Record<string, unknown>;
type JsonObject = Record<string, unknown>;

Deno.serve(async (request) => {
  if (request.method !== "POST") {
    return jsonResponse({
      success: false,
      error: "Method not allowed.",
      status_code: 405,
    }, 405);
  }

  const authError = authorizeOperator(request);
  if (authError) {
    return jsonResponse(authError, Number(authError.status_code || 403));
  }

  let body: RequestBody;
  try {
    body = await request.json();
  } catch (_error) {
    return jsonResponse({
      success: false,
      error: "Request body must be JSON.",
      status_code: 400,
    }, 400);
  }

  const action = String(body.action || "");
  const requestedRoutingValue = String(body.routing_value || "americas")
    .toLowerCase();
  const useStub = Boolean(body.use_stub ?? true);

  if (!TOURNAMENT_ROUTING_VALUES.has(requestedRoutingValue)) {
    return jsonResponse({
      success: false,
      error: "Unsupported Riot routing value.",
      status_code: 400,
    }, 400);
  }
  const routingConfig = getTournamentRoutingValue(requestedRoutingValue);
  if (!routingConfig.ok) {
    return jsonResponse({
      success: false,
      error: routingConfig.error,
      status_code: 500,
    }, 500);
  }
  const routingValue = routingConfig.value;

  const apiKey = Deno.env.get("RIOT_API_KEY") || "";
  if (!apiKey) {
    return jsonResponse({
      success: false,
      error: "RIOT_API_KEY is not configured.",
      status_code: 500,
    }, 500);
  }

  try {
    if (action === "create_provider") {
      return await createProvider(apiKey, routingValue, useStub, body);
    }
    if (action === "create_tournament") {
      return await createTournament(apiKey, routingValue, useStub, body);
    }
    if (action === "create_codes") {
      return await createCodes(apiKey, routingValue, useStub, body);
    }
    return jsonResponse({
      success: false,
      error: "Unsupported action.",
      status_code: 400,
    }, 400);
  } catch (error) {
    return jsonResponse({
      success: false,
      error: String(error),
      status_code: 500,
    }, 500);
  }
});

async function createProvider(
  apiKey: string,
  routingValue: string,
  useStub: boolean,
  body: RequestBody,
) {
  const region = String(body.region || "KR").toUpperCase();
  if (!/^[A-Z0-9_]{2,8}$/.test(region)) {
    return jsonResponse({
      success: false,
      error: "Invalid provider region.",
      status_code: 400,
    }, 400);
  }

  const callbackUrl = Deno.env.get("RIOT_CALLBACK_URL") || "";
  if (!isValidCallbackUrl(callbackUrl)) {
    return jsonResponse({
      success: false,
      error: "RIOT_CALLBACK_URL is not configured.",
      status_code: 500,
    }, 500);
  }

  return riotRequest(apiKey, routingValue, useStub, "/providers", {
    method: "POST",
    body: { region, url: callbackUrl },
  });
}

async function createTournament(
  apiKey: string,
  routingValue: string,
  useStub: boolean,
  body: RequestBody,
) {
  const providerId = Number(body.provider_id);
  const name = String(body.name || "My Tournament").trim();
  if (!Number.isSafeInteger(providerId) || providerId <= 0) {
    return jsonResponse({
      success: false,
      error: "Provider ID is required.",
      status_code: 400,
    }, 400);
  }
  if (!name || name.length > 120) {
    return jsonResponse({
      success: false,
      error: "Tournament name is invalid.",
      status_code: 400,
    }, 400);
  }

  return riotRequest(apiKey, routingValue, useStub, "/tournaments", {
    method: "POST",
    body: { name, providerId },
  });
}

async function createCodes(
  apiKey: string,
  routingValue: string,
  useStub: boolean,
  body: RequestBody,
) {
  const tournamentId = Number(body.tournament_id);
  const count = Number(body.count || 1);
  const teamSize = Number(body.team_size || 5);
  const mapType = String(body.map_type || "SUMMONERS_RIFT");
  const pickType = String(body.pick_type || "TOURNAMENT_DRAFT");
  const spectatorType = String(body.spectator_type || "ALL");
  const metadata = String(body.metadata || "");

  if (!Number.isSafeInteger(tournamentId) || tournamentId <= 0) {
    return jsonResponse({
      success: false,
      error: "Tournament ID is required.",
      status_code: 400,
    }, 400);
  }
  if (!Number.isSafeInteger(count) || count < 1 || count > 1000) {
    return jsonResponse({
      success: false,
      error: "Code count must be between 1 and 1000.",
      status_code: 400,
    }, 400);
  }
  if (!Number.isSafeInteger(teamSize) || teamSize < 1 || teamSize > 5) {
    return jsonResponse({
      success: false,
      error: "Team size must be between 1 and 5.",
      status_code: 400,
    }, 400);
  }
  if (
    !MAP_TYPES.has(mapType) || !PICK_TYPES.has(pickType) ||
    !SPECTATOR_TYPES.has(spectatorType)
  ) {
    return jsonResponse({
      success: false,
      error: "Unsupported tournament code option.",
      status_code: 400,
    }, 400);
  }

  const callbackMetadata = await buildCallbackMetadata(metadata, useStub);
  if (!callbackMetadata.ok) {
    return jsonResponse({
      success: false,
      error: callbackMetadata.error,
      status_code: 500,
    }, 500);
  }

  return riotRequest(
    apiKey,
    routingValue,
    useStub,
    `/codes?count=${count}&tournamentId=${tournamentId}`,
    {
      method: "POST",
      body: {
        mapType,
        pickType,
        spectatorType,
        teamSize,
        metadata: callbackMetadata.value,
      },
    },
  );
}

async function buildCallbackMetadata(metadata: string, useStub: boolean) {
  const callbackSecret = (Deno.env.get("RIOT_CALLBACK_SECRET") || "").trim();
  const label = metadata.trim().slice(0, CALLBACK_METADATA_LABEL_LIMIT);
  if (!callbackSecret) {
    if (!useStub) {
      return {
        ok: false,
        error:
          "RIOT_CALLBACK_SECRET is required before using the live Tournament API.",
      };
    }
    return { ok: true, value: label };
  }

  const version = 1;
  const issuedAt = Date.now();
  const nonce = crypto.randomUUID();
  const signedText = `${version}.${issuedAt}.${nonce}`;
  const signature = await hmacSha256Hex(callbackSecret, signedText);
  return {
    ok: true,
    value: JSON.stringify({
      v: version,
      ts: issuedAt,
      nonce,
      sig: signature,
      label,
    }),
  };
}

async function riotRequest(
  apiKey: string,
  routingValue: string,
  useStub: boolean,
  suffix: string,
  options: { method: string; body: Record<string, unknown> },
) {
  const basePath = useStub ? "/lol/tournament-stub/v5" : "/lol/tournament/v5";
  const riotUrl =
    `https://${routingValue}.api.riotgames.com${basePath}${suffix}`;
  const response = await fetch(riotUrl, {
    method: options.method,
    headers: {
      "X-Riot-Token": apiKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(options.body),
  });

  const responseText = await response.text();
  const parsed = parseJsonOrText(responseText);

  if (!response.ok) {
    const retryAfterHeader = response.headers.get("Retry-After");
    const retryAfter = retryAfterHeader === null
      ? null
      : Number(retryAfterHeader);
    return jsonResponse({
      success: false,
      error: extractErrorMessage(parsed, response.status, {
        useStub,
        routingValue,
      }),
      status:
        typeof parsed === "object" && parsed !== null && "status" in parsed
          ? (parsed as Record<string, unknown>).status
          : { status_code: response.status, message: String(parsed) },
      status_code: response.status,
      retryable: RETRYABLE_STATUS_CODES.has(response.status),
      retry_after: retryAfter !== null && Number.isFinite(retryAfter)
        ? retryAfter
        : null,
    }, response.status);
  }

  return jsonResponse({ success: true, data: parsed });
}

function authorizeOperator(request: Request): JsonObject | null {
  const allowedEmails = (Deno.env.get("ALLOWED_OPERATOR_EMAILS") || "")
    .split(",")
    .map((email) => email.trim().toLowerCase())
    .filter(Boolean);
  if (allowedEmails.length === 0) {
    return {
      success: false,
      error: "ALLOWED_OPERATOR_EMAILS is not configured.",
      status_code: 500,
    };
  }

  const authHeader = request.headers.get("Authorization") || "";
  const token = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : "";
  const claims = decodeJwtPayload(token);
  const email = String(claims.email || "").toLowerCase();
  if (!email || !allowedEmails.includes(email)) {
    return {
      success: false,
      error: "Operator is not authorized.",
      status_code: 403,
    };
  }
  return null;
}

function decodeJwtPayload(token: string): Record<string, unknown> {
  try {
    const payload = token.split(".")[1] || "";
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    return JSON.parse(atob(padded));
  } catch (_error) {
    return {};
  }
}

function isValidCallbackUrl(callbackUrl: string) {
  try {
    const url = new URL(callbackUrl);
    return url.protocol === "https:";
  } catch (_error) {
    return false;
  }
}

function parseJsonOrText(text: string) {
  try {
    return JSON.parse(text);
  } catch (_error) {
    return text;
  }
}

function getTournamentRoutingValue(
  requestedRoutingValue: string,
): { ok: true; value: string } | { ok: false; error: string } {
  const configured = (Deno.env.get("RIOT_TOURNAMENT_ROUTING") || "").trim()
    .toLowerCase();
  const value = configured || requestedRoutingValue || "americas";
  if (TOURNAMENT_ROUTING_VALUES.has(value)) {
    return { ok: true, value };
  }
  return {
    ok: false,
    error:
      "RIOT_TOURNAMENT_ROUTING must be one of americas, asia, europe, or sea.",
  };
}

async function hmacSha256Hex(secret: string, message: string) {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode(message),
  );
  return [...new Uint8Array(signature)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function extractErrorMessage(
  parsed: unknown,
  statusCode: number,
  context: { useStub: boolean; routingValue: string },
) {
  const statusMessage = extractRiotStatusMessage(parsed, statusCode);
  if (statusCode === 403) {
    const apiName = context.useStub ? "Tournament Stub API" : "Tournament API";
    return `${statusMessage}. Riot returned 403 for ${apiName} through ${context.routingValue}.api.riotgames.com. This project is verified with americas.api.riotgames.com; if Riot instructs another Tournament API routing host after approval, set RIOT_TOURNAMENT_ROUTING in Supabase secrets. Also check that the Supabase RIOT_API_KEY secret is the intended Riot key.`;
  }
  return statusMessage;
}

function extractRiotStatusMessage(parsed: unknown, statusCode: number) {
  if (typeof parsed === "object" && parsed !== null && "status" in parsed) {
    const status = (parsed as Record<string, unknown>).status as Record<
      string,
      unknown
    >;
    if (status && status.message) {
      return `Riot API Error ${String(status.status_code || statusCode)}: ${
        String(status.message)
      }`;
    }
  }
  return `Riot API Error ${statusCode}`;
}

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
