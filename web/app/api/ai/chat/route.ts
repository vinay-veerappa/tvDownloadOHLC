import { NextRequest, NextResponse } from "next/server"

// Types
interface ChatMessage {
    role: "user" | "assistant" | "system"
    content: string
}

interface ChatRequest {
    messages: ChatMessage[]
    provider?: "gemini" | "ollama"
    model?: string
    context?: {
        trades?: any[]
        summary?: any
    }
}

// Gemini API configuration
const GEMINI_API_KEY = process.env.GEMINI_API_KEY
const GEMINI_MODEL = "gemini-2.0-flash"
const GEMINI_URL = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent`

// Ollama configuration (local)
const OLLAMA_URL = process.env.OLLAMA_URL || "http://localhost:11434"
const OLLAMA_MODEL = process.env.OLLAMA_MODEL || "llama3.2"

// System prompt for trading assistant
const SYSTEM_PROMPT = `You are a trading journal AI assistant. You help traders analyze their performance, identify patterns, and improve their trading.

You have access to the trader's journal data including:
- Trade history (entries, exits, P&L)
- Performance metrics (win rate, profit factor, equity curve)
- Strategy performance
- Market context (VIX, economic events)

Be concise, data-driven, and actionable in your responses. Focus on:
1. Pattern recognition in winning/losing trades
2. Risk management insights
3. Emotional and behavioral patterns
4. Strategy optimization suggestions

When analyzing trades, consider:
- Time of day patterns
- Position sizing
- Stop loss/take profit discipline
- Market conditions during trades`

export async function POST(request: NextRequest) {
    try {
        const body: ChatRequest = await request.json()
        const { messages, provider = "gemini", model, context } = body

        if (!messages || messages.length === 0) {
            return NextResponse.json(
                { error: "Messages are required" },
                { status: 400 }
            )
        }

        // Build context-aware messages
        let contextMessage = ""
        if (context?.trades) {
            contextMessage += `\n\nRecent trades data:\n${JSON.stringify(context.trades.slice(0, 20), null, 2)}`
        }
        if (context?.summary) {
            contextMessage += `\n\nPerformance summary:\n${JSON.stringify(context.summary, null, 2)}`
        }

        const fullMessages: ChatMessage[] = [
            { role: "system", content: SYSTEM_PROMPT + contextMessage },
            ...messages
        ]

        // Route to appropriate provider
        if (provider === "ollama") {
            return await handleOllama(fullMessages, model || OLLAMA_MODEL)
        } else {
            return await handleGemini(fullMessages)
        }
    } catch (error) {
        console.error("AI Chat error:", error)
        return NextResponse.json(
            { error: "Failed to process request" },
            { status: 500 }
        )
    }
}

async function handleGemini(messages: ChatMessage[]) {
    if (!GEMINI_API_KEY) {
        return NextResponse.json(
            { error: "Gemini API key not configured. Set GEMINI_API_KEY in .env.local" },
            { status: 500 }
        )
    }

    // Convert to Gemini format
    const contents = messages
        .filter(m => m.role !== "system")
        .map(m => ({
            role: m.role === "assistant" ? "model" : "user",
            parts: [{ text: m.content }]
        }))

    // Add system instruction
    const systemInstruction = messages.find(m => m.role === "system")?.content || ""

    const response = await fetch(`${GEMINI_URL}?key=${GEMINI_API_KEY}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            contents,
            systemInstruction: { parts: [{ text: systemInstruction }] },
            generationConfig: {
                temperature: 0.7,
                maxOutputTokens: 2048,
            }
        })
    })

    if (!response.ok) {
        const error = await response.text()
        console.error("Gemini error:", error)
        return NextResponse.json(
            { error: "Gemini API error" },
            { status: response.status }
        )
    }

    const data = await response.json()
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text || ""

    return NextResponse.json({
        message: text,
        provider: "gemini",
        model: GEMINI_MODEL
    })
}

async function handleOllama(messages: ChatMessage[], model: string) {
    try {
        // Convert to Ollama format
        const ollamaMessages = messages.map(m => ({
            role: m.role,
            content: m.content
        }))

        const response = await fetch(`${OLLAMA_URL}/api/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                model,
                messages: ollamaMessages,
                stream: false
            })
        })

        if (!response.ok) {
            throw new Error(`Ollama error: ${response.status}`)
        }

        const data = await response.json()
        const text = data.message?.content || ""

        return NextResponse.json({
            message: text,
            provider: "ollama",
            model
        })
    } catch (error) {
        console.error("Ollama error:", error)
        return NextResponse.json(
            { error: "Ollama not available. Make sure Ollama is running locally." },
            { status: 503 }
        )
    }
}
