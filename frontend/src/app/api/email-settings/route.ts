import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { resolveClientName } from "@/lib/server-config";

function deriveModalUrl(label: string) {
  const dashboardUrl = process.env.MODAL_API_BASE_URL;
  if (!dashboardUrl) return null;
  return dashboardUrl.replace("--api-dashboard", `--${label}`);
}

async function parseModalResponse(response: Response) {
  const payload = await response.json().catch(() => ({}));
  return NextResponse.json(payload, { status: response.status });
}

export async function GET(request: Request) {
  const { userId } = await auth();

  if (!userId) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const resolvedClient = resolveClientName(searchParams.get("client"));
  if (!resolvedClient.ok) {
    return NextResponse.json({ error: resolvedClient.error }, { status: resolvedClient.status });
  }

  const modalUrl = process.env.MODAL_EMAIL_SETTINGS_URL || deriveModalUrl("api-email-settings");
  const apiKey = process.env.ADSPULSE_INTERNAL_API_KEY;

  if (!modalUrl || !apiKey) {
    return NextResponse.json({ error: "Modal email settings API is not configured" }, { status: 500 });
  }

  const params = new URLSearchParams({ client_name: resolvedClient.clientName });
  const response = await fetch(`${modalUrl}?${params.toString()}`, {
    headers: { "x-api-key": apiKey },
    cache: "no-store",
  });

  return parseModalResponse(response);
}

export async function POST(request: Request) {
  const { userId } = await auth();

  if (!userId) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  const body = await request.json().catch(() => ({}));
  const resolvedClient = resolveClientName(body.client_name);
  if (!resolvedClient.ok) {
    return NextResponse.json({ error: resolvedClient.error }, { status: resolvedClient.status });
  }

  const modalUrl = process.env.MODAL_EMAIL_SETTINGS_UPDATE_URL || deriveModalUrl("api-email-settings-update");
  const apiKey = process.env.ADSPULSE_INTERNAL_API_KEY;

  if (!modalUrl || !apiKey) {
    return NextResponse.json({ error: "Modal email settings API is not configured" }, { status: 500 });
  }

  const response = await fetch(modalUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
    },
    body: JSON.stringify({
      ...body,
      client_name: resolvedClient.clientName,
    }),
  });

  return parseModalResponse(response);
}
