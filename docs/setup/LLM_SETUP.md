# LLM Setup & Usage Guide

This guide explains how to set up and run the Local LLM (Large Language Model) integration for the Trading Journal AI Assistant.

## Prerequisites

1.  **Ollama**: We use Ollama to run local models efficiently.
    *   **Download**: [https://ollama.com/download](https://ollama.com/download)
    *   **Install**: Follow the installer instructions for Windows.

## Quick Start

1.  **Start Ollama**:
    *   Once installed, Ollama usually runs in the background tray.
    *   To verify or start a model session interactively, run:
        ```cmd
        .\start_llm.bat
        ```
    *   This script will attempt to pull (if missing) and run the `llama3` model.

2.  **Verify Model**:
    *   The `start_llm.bat` script runs `ollama run llama3`.
    *   You should see a prompt `>>>` where you can chat directly with the model to test it.

## Configuration

The application connects to Ollama via the default port `11434`.

*   **API Endpoint**: `http://localhost:11434`
*   **Default Model**: `llama3` (Configurable in `web/.env` if needed, though currently hardcoded in `api/routers/ai.py` or similar).

## Troubleshooting

*   **"ollama is not recognized"**: Ensure Ollama is added to your system PATH (the installer usually does this). Restart your terminal.
*   **Connection Refused**: Make sure Ollama is actually running (check system tray).
*   **Slow Performance**: Local LLMs depend heavily on GPU/RAM. Ensure you have enough resources. `llama3:8b` typically requires ~8GB+ RAM.

## System Integration

The Trading Journal `web` app communicates with the `api` backend (FastAPI), which in turn calls the local Ollama instance.

1.  **Frontend (`web`)**: Sends chat request to Next.js API route.
2.  **Backend (`api`)**: Receives request, formats prompt with context (trades, strategies), and queries Ollama.
3.  **Ollama**: Generates response and streams it back.

---
**Status**: Verified working with Ollama v0.1.x and `llama3`.
