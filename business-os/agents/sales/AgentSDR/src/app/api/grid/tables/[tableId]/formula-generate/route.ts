import { NextRequest, NextResponse } from "next/server";
import { FormulaGeneratorUnavailableError, generateFormula } from "@/lib/grid/formula-generator";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { isRecord, isUuid } from "@/lib/grid/validate";

export async function POST(request: NextRequest, { params }: { params: Promise<{ tableId: string }> }) {
  try {
    return await withOrgContext(request, async () => {
      const { tableId } = await params;
      if (!isUuid(tableId)) return NextResponse.json({ error: "table not found" }, { status: 404 });
      let body: { prompt?: unknown; currentExpression?: unknown };
      try {
        const parsed = await request.json();
        if (!isRecord(parsed)) throw new Error("not an object");
        body = parsed;
      } catch { return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 }); }
      if (typeof body.prompt !== "string" || (body.currentExpression !== undefined && typeof body.currentExpression !== "string")) {
        return NextResponse.json({ error: "prompt and currentExpression must be text" }, { status: 400 });
      }
      const prompt = body.prompt.trim();
      if (!prompt) return NextResponse.json({ error: "Describe the formula you want" }, { status: 400 });
      if (prompt.length > 2_000 || (body.currentExpression?.length ?? 0) > 10_000) return NextResponse.json({ error: "Formula request is too long" }, { status: 400 });
      try {
        return NextResponse.json(await generateFormula(tableId, prompt, body.currentExpression));
      } catch (error) {
        const rawMessage = error instanceof Error ? error.message : "Could not generate formula";
        const connectionFailure = /connection error|unable to connect|fetch failed|could not resolve/i.test(rawMessage);
        const message = connectionFailure
          ? "Could not reach the AI formula service. Check the configured OpenAI/Azure endpoint."
          : rawMessage;
        return NextResponse.json(
          { error: message },
          { status: error instanceof FormulaGeneratorUnavailableError ? 503 : connectionFailure ? 502 : 422 },
        );
      }
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
