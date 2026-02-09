# Ray Architecture

## 1. Overview
The `Ray` utility draws a line segment that starts at one point and extends infinitely in the direction of the second point.

## 2. Key Responsibilities
- **Infinite Extension**: Calculates the intersection with the chart boundaries to simulate an infinite line.
- **Rendering**: Draws the starting point and the extended line.
- **Interaction**: Provides handles at the start and direction points.

## 3. Data Flow
[Points] -> [RayV2] -> [Extrapolation Logic] -> [Renderer]

## 4. Key Components
- **RayV2**: Manages the ray's origin and direction.
- **RayRenderer**: Handles the infinite line drawing logic.

## 5. Technology & Constraints
- **Calculation**: Requires robust coordinate clipping to prevent infinite canvas values.

## 6. Diagram
```mermaid
graph LR;
    P0[Origin]-->P1[Direction];
    P1-->Infinite[Infinite Extension];
```
