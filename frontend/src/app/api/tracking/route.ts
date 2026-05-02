import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { resolveClientName } from "@/lib/server-config";

export async function GET(request: Request) {
  const { userId } = await auth();
  if (!userId) return new NextResponse("Unauthorized", { status: 401 });

  const { searchParams } = new URL(request.url);
  const resolvedClient = resolveClientName(searchParams.get("client_name"));

  if (!resolvedClient.ok) {
    return NextResponse.json({ error: resolvedClient.error }, { status: resolvedClient.status });
  }
  const clientName = resolvedClient.clientName;

  try {
    const modalBaseUrl = process.env.MODAL_TRACKING_URL;
    const apiKey = process.env.ADSPULSE_INTERNAL_API_KEY;

    if (!modalBaseUrl || !apiKey) {
      return NextResponse.json({ error: "Modal tracking API is not configured" }, { status: 500 });
    }

    const modalUrl = `${modalBaseUrl}?client_name=${encodeURIComponent(clientName)}`;

    const response = await fetch(modalUrl, {
      headers: { "x-api-key": apiKey },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: "Failed to fetch tracking data" }));
      return NextResponse.json(error, { status: response.status });
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Tracking Data Error:", error);
    return NextResponse.json({ error: "Failed to load tracking data" }, { status: 500 });
  }
}

export async function POST(request: Request) {
  const { userId } = await auth();
  if (!userId) return new NextResponse("Unauthorized", { status: 401 });

  try {
    const body = await request.json();
    const resolvedClient = resolveClientName(body.client_name);
    if (!resolvedClient.ok) {
      return NextResponse.json({ error: resolvedClient.error }, { status: resolvedClient.status });
    }

    const modalUrl = process.env.MODAL_APPLY_URL;
    const apiKey = process.env.ADSPULSE_INTERNAL_API_KEY;

    if (!modalUrl || !apiKey) {
      return NextResponse.json({ error: "Modal apply API is not configured" }, { status: 500 });
    }

    const response = await fetch(modalUrl, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "x-api-key": apiKey 
      },
      body: JSON.stringify({ ...body, client_name: resolvedClient.clientName }),
    });

    const result = await response.json();
    return NextResponse.json(result, { status: response.status });
  } catch (error) {
    console.error("Apply Recommendation Error:", error);
    return NextResponse.json({ error: "Failed to apply recommendation" }, { status: 500 });
  }
}

export async function DELETE(request: Request) {
  const { userId } = await auth();
  if (!userId) return new NextResponse("Unauthorized", { status: 401 });

  const { searchParams } = new URL(request.url);
  const recommendationId = searchParams.get("recommendation_id");
  const resolvedClient = resolveClientName(searchParams.get("client_name"));

  if (!recommendationId) return new NextResponse("Missing recommendation_id", { status: 400 });
  if (!resolvedClient.ok) {
    return NextResponse.json({ error: resolvedClient.error }, { status: resolvedClient.status });
  }
  const clientName = resolvedClient.clientName;

  try {
    const modalBaseUrl = process.env.MODAL_TRACKING_DELETE_URL;
    const apiKey = process.env.ADSPULSE_INTERNAL_API_KEY;

    if (!modalBaseUrl || !apiKey) {
      return NextResponse.json({ error: "Modal tracking delete API is not configured" }, { status: 500 });
    }

    const modalUrl = `${modalBaseUrl}?recommendation_id=${encodeURIComponent(recommendationId)}&client_name=${encodeURIComponent(clientName)}`;

    const response = await fetch(modalUrl, {
      method: "DELETE",
      headers: { "x-api-key": apiKey },
    });

    const result = await response.json();
    return NextResponse.json(result, { status: response.status });
  } catch (error) {
    console.error("Delete Tracking Error:", error);
    return NextResponse.json({ error: "Failed to delete tracking item" }, { status: 500 });
  }
}
