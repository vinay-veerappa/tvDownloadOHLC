"use client"

import { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from "@/components/ui/select"
import {
    Bot, Send, Loader2, User, Sparkles, TrendingUp, AlertCircle, Settings2
} from "lucide-react"
import { getAnalyticsSummary } from "@/actions/analytics-actions"
import { getTrades } from "@/actions/trade-actions"

interface Message {
    id: string
    role: "user" | "assistant"
    content: string
    timestamp: Date
}

interface AIChatProps {
    embedded?: boolean // If true, show as sidebar style
}

// Available Ollama models
const OLLAMA_MODELS = [
    { id: "llama3.2:latest", name: "Llama 3.2", description: "Fast, 2GB" },
    { id: "gemma3:latest", name: "Gemma 3", description: "Google, 3.3GB" },
    { id: "mistral:latest", name: "Mistral", description: "Coding, 4.4GB" },
    { id: "qwen3-vl:latest", name: "Qwen3 VL", description: "Vision, 6.1GB" },
]

const QUICK_PROMPTS = [
    { label: "📊 Summarize today", prompt: "Summarize my trades today" },
    { label: "📉 Losing patterns", prompt: "What patterns do you see in my losing trades?" },
    { label: "🏆 Best strategy", prompt: "Which strategy is performing best?" },
    { label: "⚠️ Risk review", prompt: "Review my risk management this week" },
    { label: "💡 Improvement tips", prompt: "What should I focus on improving?" },
]

export function AIChat({ embedded = false }: AIChatProps) {
    const [messages, setMessages] = useState<Message[]>([])
    const [input, setInput] = useState("")
    const [loading, setLoading] = useState(false)
    const [provider, setProvider] = useState<"gemini" | "ollama">("gemini")
    const [ollamaModel, setOllamaModel] = useState("llama3.2:latest")
    const [error, setError] = useState<string | null>(null)
    const scrollRef = useRef<HTMLDivElement>(null)
    const inputRef = useRef<HTMLInputElement>(null)

    // Auto-scroll to bottom
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
    }, [messages])

    // Focus input on mount
    useEffect(() => {
        inputRef.current?.focus()
    }, [])

    const sendMessage = async (content: string) => {
        if (!content.trim() || loading) return

        setError(null)
        const userMessage: Message = {
            id: Date.now().toString(),
            role: "user",
            content: content.trim(),
            timestamp: new Date()
        }

        setMessages(prev => [...prev, userMessage])
        setInput("")
        setLoading(true)

        try {
            // Fetch context data
            const [summaryResult, tradesResult] = await Promise.all([
                getAnalyticsSummary(),
                getTrades()
            ])

            const context = {
                summary: summaryResult.success ? summaryResult.data : undefined,
                trades: tradesResult.success ? tradesResult.data : undefined
            }

            // Send to API
            const response = await fetch("/api/ai/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    messages: [...messages, userMessage].map(m => ({
                        role: m.role,
                        content: m.content
                    })),
                    provider,
                    model: provider === "ollama" ? ollamaModel : undefined,
                    context
                })
            })

            const data = await response.json()

            if (!response.ok) {
                throw new Error(data.error || "Failed to get response")
            }

            const assistantMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: "assistant",
                content: data.message,
                timestamp: new Date()
            }

            setMessages(prev => [...prev, assistantMessage])
        } catch (err) {
            setError(err instanceof Error ? err.message : "Something went wrong")
        } finally {
            setLoading(false)
        }
    }

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        sendMessage(input)
    }

    const handleQuickPrompt = (prompt: string) => {
        sendMessage(prompt)
    }

    return (
        <Card className={embedded ? "h-full border-0 rounded-none" : "h-[600px]"}>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                        <Bot className="h-5 w-5" />
                        Trading AI Assistant
                    </CardTitle>
                    <div className="flex items-center gap-2">
                        {/* Model selector for Ollama */}
                        {provider === "ollama" && (
                            <Select value={ollamaModel} onValueChange={setOllamaModel}>
                                <SelectTrigger className="w-[140px] h-8">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {OLLAMA_MODELS.map(m => (
                                        <SelectItem key={m.id} value={m.id}>
                                            <span className="flex flex-col">
                                                <span>{m.name}</span>
                                                <span className="text-xs text-muted-foreground">{m.description}</span>
                                            </span>
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        )}
                        {/* Provider selector */}
                        <Select value={provider} onValueChange={(v) => setProvider(v as "gemini" | "ollama")}>
                            <SelectTrigger className="w-[120px] h-8">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="gemini">
                                    <span className="flex items-center gap-1">
                                        <Sparkles className="h-3 w-3" /> Gemini
                                    </span>
                                </SelectItem>
                                <SelectItem value="ollama">
                                    <span className="flex items-center gap-1">
                                        <Settings2 className="h-3 w-3" /> Ollama
                                    </span>
                                </SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>
            </CardHeader>
            <CardContent className="flex flex-col h-[calc(100%-80px)]">
                {/* Messages */}
                <ScrollArea className="flex-1 pr-4" ref={scrollRef}>
                    {messages.length === 0 ? (
                        <div className="text-center py-8">
                            <Bot className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                            <h3 className="font-medium mb-2">How can I help you today?</h3>
                            <p className="text-sm text-muted-foreground mb-4">
                                Ask me about your trading performance, patterns, or strategies.
                            </p>
                            <div className="flex flex-wrap gap-2 justify-center">
                                {QUICK_PROMPTS.map((qp, i) => (
                                    <Button
                                        key={i}
                                        variant="outline"
                                        size="sm"
                                        onClick={() => handleQuickPrompt(qp.prompt)}
                                    >
                                        {qp.label}
                                    </Button>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {messages.map((msg) => (
                                <div
                                    key={msg.id}
                                    className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}
                                >
                                    {msg.role === "assistant" && (
                                        <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                                            <Bot className="h-4 w-4 text-primary" />
                                        </div>
                                    )}
                                    <div
                                        className={`rounded-lg px-4 py-2 max-w-[80%] ${msg.role === "user"
                                            ? "bg-primary text-primary-foreground"
                                            : "bg-muted"
                                            }`}
                                    >
                                        <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                                    </div>
                                    {msg.role === "user" && (
                                        <div className="h-8 w-8 rounded-full bg-secondary flex items-center justify-center shrink-0">
                                            <User className="h-4 w-4" />
                                        </div>
                                    )}
                                </div>
                            ))}
                            {loading && (
                                <div className="flex gap-3">
                                    <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                                        <Loader2 className="h-4 w-4 animate-spin text-primary" />
                                    </div>
                                    <div className="rounded-lg px-4 py-2 bg-muted">
                                        <p className="text-sm text-muted-foreground">Thinking...</p>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </ScrollArea>

                {/* Error */}
                {error && (
                    <div className="flex items-center gap-2 text-sm text-red-500 py-2">
                        <AlertCircle className="h-4 w-4" />
                        {error}
                    </div>
                )}

                {/* Input */}
                <form onSubmit={handleSubmit} className="flex gap-2 pt-4">
                    <Input
                        ref={inputRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Ask about your trading..."
                        disabled={loading}
                        className="flex-1"
                    />
                    <Button type="submit" disabled={!input.trim() || loading}>
                        <Send className="h-4 w-4" />
                    </Button>
                </form>
            </CardContent>
        </Card>
    )
}
