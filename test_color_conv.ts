function toHex(color: string): string {
    if (!color) return "#000000";

    // Handle hex
    if (color.startsWith("#")) {
        if (color.length === 7) return color;
        if (color.length === 4) {
            return "#" + color[1] + color[1] + color[2] + color[2] + color[3] + color[3];
        }
        // Handle #RRGGBBAA? Input type color ignores alpha, so strictly it should be 7 chars.
        if (color.length > 7) return color.substring(0, 7);
        return color;
    }

    // Handle rgb/rgba
    if (color.startsWith("rgb")) {
        const match = color.match(/\d+/g);
        if (match && match.length >= 3) {
            const r = parseInt(match[0]);
            const g = parseInt(match[1]);
            const b = parseInt(match[2]);
            return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
        }
    }

    // Handle named colors (basic list or fallback)
    if (color === "transparent") return "#000000";
    if (color === "white") return "#ffffff";
    if (color === "black") return "#000000";
    if (color === "red") return "#ff0000";
    if (color === "green") return "#008000";
    if (color === "blue") return "#0000ff";

    // Fallback
    return "#000000";
}

// Test cases
console.log(toHex("rgba(41, 98, 255, 0.15)")); // Expected: #2962ff
console.log(toHex("rgb(41, 98, 255)"));       // Expected: #2962ff
console.log(toHex("#fff"));                   // Expected: #ffffff
console.log(toHex("#123456"));                // Expected: #123456
console.log(toHex("transparent"));            // Expected: #000000
