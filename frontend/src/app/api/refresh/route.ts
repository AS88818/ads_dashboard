import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { resolveClientName } from "@/lib/server-config";

function isValidIsoDate(value: unknown) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }

  const [year, month, day] = value.split("-").map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return (
    parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day
  );
}

export async function POST(request: Request) {
  const { userId } = await auth();

  if (!userId) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  const modalUrl = process.env.MODAL_REFRESH_URL;
  const apiKey = process.env.ADSPULSE_INTERNAL_API_KEY;

  if (!modalUrl || !apiKey) {
    return NextResponse.json({ error: "Modal refresh API is not configured" }, { status: 500 });
  }

  const body = await request.json().catch(() => ({}));
  const resolvedClient = resolveClientName(body.client_name);
  if (!resolvedClient.ok) {
    return NextResponse.json({ error: resolvedClient.error }, { status: resolvedClient.status });
  }
  const clientName = resolvedClient.clientName;
  const hasCustomRange = body.start_date || body.end_date;

  if (hasCustomRange && (!isValidIsoDate(body.start_date) || !isValidIsoDate(body.end_date))) {
    return NextResponse.json({ error: "start_date and end_date must use YYYY-MM-DD format" }, { status: 400 });
  }

  if (hasCustomRange && body.start_date > body.end_date) {
    return NextResponse.json({ error: "start_date must be before or equal to end_date" }, { status: 400 });
  }

  const response = await fetch(modalUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
    },
    body: JSON.stringify({
      client_name: clientName,
      days: body.days,
      start_date: hasCustomRange ? body.start_date : undefined,
      end_date: hasCustomRange ? body.end_date : undefined,
    }),
  });

  const result = await response.json().catch(() => ({ status: response.ok ? "triggered" : "error" }));
  return NextResponse.json(result, { status: response.status });
}
