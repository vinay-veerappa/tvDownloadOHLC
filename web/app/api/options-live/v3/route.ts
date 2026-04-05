import { NextRequest } from "next/server";
import { ok, readSymbol } from "@/lib/options-live-v3/http";
import { V3_API_ENDPOINTS } from "@/lib/options-live-v3/contracts/endpoints";

export async function GET(req: NextRequest) {
  const symbol = readSymbol(req);
  return ok(
    {
      implemented: true,
      namespace: "options-live-v3",
      endpoints: V3_API_ENDPOINTS,
    },
    symbol
  );
}
