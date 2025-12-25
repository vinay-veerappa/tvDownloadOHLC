declare module 'dom-to-image-more' {
    interface Options {
        quality?: number;
        bgcolor?: string;
        style?: Record<string, string>;
        filter?: (node: Node) => boolean;
        width?: number;
        height?: number;
    }

    export function toPng(node: Node, options?: Options): Promise<string>;
    export function toJpeg(node: Node, options?: Options): Promise<string>;
    export function toBlob(node: Node, options?: Options): Promise<Blob>;
    export function toPixelData(node: Node, options?: Options): Promise<Uint8ClampedArray>;
    export function toSvg(node: Node, options?: Options): Promise<string>;
}
