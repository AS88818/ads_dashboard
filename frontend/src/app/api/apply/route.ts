import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const { userId } = await auth();

  if (!userId) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  try {
    const body = await request.json();
    const modalUrl = process.env.MODAL_APPLY_URL;
    const apiKey = process.env.ADSPULSE_INTERNAL_API_KEY;

    if (!modalUrl || !apiKey) {
      return NextResponse.json({ error: "Modal apply API is not configured" }, { status: 500 });
    }

    const response = await fetch(modalUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
      },
      body: JSON.stringify(body),
    });

    const result = await response.json();
    return NextResponse.json(result, { status: response.status });
  } catch (error) {
    console.error("Apply Recommendation Error:", error);
    return NextResponse.json({ error: "Failed to apply recommendation" }, { status: 500 });
  }
}
