# HorizontalRay Architecture

## 1. Overview
A `HorizontalRay` starts at a specific price/time point and extends horizontally to the right (future) infinitely.

## 2. Key Responsibilities
- **Unidirectional Extension**: Anchors at a point and projects strictly to the right.
- **Level Identification**: Used for marking key breakouts or support/resistance starting points.

## 3. Data Flow
[Start Point] -> [Right-bound Projection] -> [Renderer]

## 4. Diagram
```mermaid
graph LR;
    Start-->Right[Infinite Right Extension];
```
