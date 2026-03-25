@echo off
echo Starting Ollama LLM Server...
echo Ensure Ollama is installed and running (default port 11434).
echo If not installed, download from https://ollama.com/
echo.
echo Pulling/Running llama3 model...
SET "CUDA_VISIBLE_DEVICES=GPU-2cf1d779-fa07-93dd-9667-d77c9a02f411"
ollama run gemini-3-flash-preview
ollama run qwen3
pause
