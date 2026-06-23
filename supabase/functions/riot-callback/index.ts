const CALLBACK_METADATA_MAX_AGE_MS = 120 * 24 * 60 * 60 * 1000;

Deno.serve(async (request) => {
  if (request.method !== "POST") {
    return jsonResponse({
      success: false,
      error: "Method not allowed.",
      status_code: 405,
    }, 405);
  }

  try {
    const payload = await request.json();
    const metadataVerification = await verifyCallbackMetadata(payload.metaData);
    if (!metadataVerification.ok) {
      console.warn(
        "riot_tournament_callback_rejected",
        JSON.stringify({
          reason: metadataVerification.error,
          shortCode: payload.shortCode ?? null,
          receivedAt: new Date().toISOString(),
        }),
      );
      return jsonResponse({
        success: false,
        error: metadataVerification.error,
        status_code: 400,
      }, 400);
    }

    console.log(
      "riot_tournament_callback",
      JSON.stringify({
        gameId: payload.gameId ?? null,
        shortCode: payload.shortCode ?? null,
        region: payload.region ?? null,
        metadataVerified: metadataVerification.verified,
        receivedAt: new Date().toISOString(),
      }),
    );
    return jsonResponse({ success: true });
  } catch (error) {
    console.error("riot_tournament_callback_error", String(error));
    return jsonResponse({
      success: false,
      error: "Invalid callback payload.",
      status_code: 400,
    }, 400);
  }
});

async function verifyCallbackMetadata(metaData: unknown) {
  const callbackSecret = (Deno.env.get("RIOT_CALLBACK_SECRET") || "").trim();
  if (!callbackSecret) {
    return {
      ok: false,
      error: "RIOT_CALLBACK_SECRET is not configured.",
    };
  }
  if (typeof metaData !== "string" || !metaData.trim()) {
    return { ok: false, error: "Missing callback metadata." };
  }

  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(metaData);
  } catch (_error) {
    return { ok: false, error: "Invalid callback metadata." };
  }

  const version = Number(parsed.v);
  const issuedAt = Number(parsed.ts);
  const nonce = String(parsed.nonce || "");
  const signature = String(parsed.sig || "");
  if (
    version !== 1 ||
    !Number.isSafeInteger(issuedAt) ||
    !nonce ||
    !/^[a-f0-9]{64}$/i.test(signature)
  ) {
    return { ok: false, error: "Invalid callback metadata." };
  }

  if (Math.abs(Date.now() - issuedAt) > CALLBACK_METADATA_MAX_AGE_MS) {
    return { ok: false, error: "Expired callback metadata." };
  }

  const expectedSignature = await hmacSha256Hex(
    callbackSecret,
    `${version}.${issuedAt}.${nonce}`,
  );
  if (!timingSafeEqual(signature.toLowerCase(), expectedSignature)) {
    return { ok: false, error: "Callback metadata signature mismatch." };
  }

  return { ok: true, verified: true };
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

function timingSafeEqual(a: string, b: string) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let index = 0; index < a.length; index += 1) {
    diff |= a.charCodeAt(index) ^ b.charCodeAt(index);
  }
  return diff === 0;
}

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
