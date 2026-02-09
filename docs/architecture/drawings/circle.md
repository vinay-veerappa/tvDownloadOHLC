# Circle Architecture

## 1. Overview
The `Circle` utility (often used for ellipse or circular areas) is defined by a center point and a perimeter point (radius).

## 2. Key Responsibilities
- **Radius Calculation**: Computes the distance between center and edge in screen pixels.
- **Aspect Ratio**: Handles elliptical rendering if the chart scales are non-linear.

## 3. Diagram
```mermaid
graph LR;
    Center-->Radius;
    Radius-->Circumference;
```
