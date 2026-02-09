# Brush Architecture

## 1. Overview
The `Brush` tool (and `Path` / `Highlighter`) allows for freehand drawing of non-linear paths.

## 2. Key Responsibilities
- **Point Sampling**: Efficiently captures mouse movements into a sequence of points.
- **Smoothing**: Applies simplification algorithms to maintain performance without losing detail.
- **Continuous Rendering**: Renders the path as a single multi-segment stroke.

## 3. Key Components
- **PathRenderer**: Specialized for handling large arrays of points.

## 4. Diagram
```mermaid
graph LR;
    Start-->Movement;
    Movement-->Sample[Point Capture];
    Sample-->Stroke;
```
