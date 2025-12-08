import { ISeriesPrimitive, IPrimitivePaneRenderer, IPrimitivePaneView, PrimitivePaneViewZOrder, Time, IChartApi, ISeriesApi, LogicalRange } from "lightweight-charts";
import { VolumeProfileData } from "@/lib/charts/volume-profile-calc";

// Helper for pixel snapping
function pixelSnap(start: number, end: number, pixelRatio: number) {
    const startSnap = Math.round(pixelRatio * start);
    const endSnap = Math.round(pixelRatio * end);
    return {
        position: Math.min(startSnap, endSnap),
        length: Math.abs(endSnap - startSnap) + 1
    };
}

class VolumeProfileRenderer implements IPrimitivePaneRenderer {
    _data: {
        x: number | null;
        top: number | null;
        items: { y: number | null; width: number }[];
        columnHeight: number;
        width: number;
    };

    constructor(data: any) {
        this._data = data;
    }

    draw(target: any) { // target is CanvasRenderingTarget2D
        target.useBitmapCoordinateSpace((scope: any) => {
            if (this._data.x === null || this._data.top === null) return;

            const ctx = scope.context;
            const horizontalPixelRatio = scope.horizontalPixelRatio;
            const verticalPixelRatio = scope.verticalPixelRatio;

            // Draw Bars
            ctx.fillStyle = "rgba(0, 150, 255, 0.4)"; // Blueish transclucent

            this._data.items.forEach((item: any) => {
                if (item.y === null || this._data.x === null) return;

                const yPos = pixelSnap(item.y, item.y - this._data.columnHeight, verticalPixelRatio);
                const xPos = pixelSnap(this._data.x, this._data.x + item.width, horizontalPixelRatio);

                ctx.fillRect(
                    xPos.position,
                    yPos.position,
                    xPos.length,
                    yPos.length - 1 // Gap
                );
            });
        });
    }
}

class VolumeProfilePaneView implements IPrimitivePaneView {
    _source: VolumeProfilePrimitive;
    _x: number | null = null;
    _width: number = 0;
    _columnHeight: number = 0;
    _top: number | null = null;
    _items: any[] = [];

    constructor(source: VolumeProfilePrimitive) {
        this._source = source;
    }

    zOrder(): PrimitivePaneViewZOrder {
        return 'normal'; // or 'bottom' to be behind candles
    }

    update() {
        const vpData = this._source._vpData;
        const series = this._source._series;
        const chart = this._source._chart;

        if (!vpData || !series || !chart) return;

        const timeScale = chart.timeScale();

        // Calculate X coordinate
        this._x = timeScale.timeToCoordinate(vpData.time as Time);

        // Approximate width in pixels
        this._width = timeScale.options().barSpacing * vpData.width;

        if (!vpData.profile || vpData.profile.length < 2) return;

        // Calculate Column Height
        const price1 = series.priceToCoordinate(vpData.profile[0].price) ?? 0;
        const price2 = series.priceToCoordinate(vpData.profile[1].price) ?? 0;

        this._columnHeight = Math.abs(price1 - price2);
        if (this._columnHeight < 1) this._columnHeight = 1; // Minimum 1px

        // Find max volume
        const maxVol = vpData.profile.reduce((acc, item) => Math.max(acc, item.vol), 0);

        // Map items
        this._items = vpData.profile.map(item => ({
            y: series.priceToCoordinate(item.price),
            width: (this._width * item.vol) / maxVol
        }));

        this._top = series.priceToCoordinate(vpData.profile[0].price);
    }

    renderer(): IPrimitivePaneRenderer | null {
        if (!this._source._visible) return null;

        return new VolumeProfileRenderer({
            x: this._x,
            top: this._top,
            columnHeight: this._columnHeight,
            width: this._width,
            items: this._items
        });
    }
}

export class VolumeProfilePrimitive implements ISeriesPrimitive {
    _chart: IChartApi | null = null;
    _series: ISeriesApi<any> | null = null;
    _vpData: VolumeProfileData | null = null;
    _paneViews: VolumeProfilePaneView[];
    _visible: boolean = true;

    constructor(data: VolumeProfileData) {
        this._vpData = data;
        this._paneViews = [new VolumeProfilePaneView(this)];
    }

    setData(data: VolumeProfileData) {
        this._vpData = data;
        this.updateAllViews();
    }

    setVisible(visible: boolean) {
        this._visible = visible;
        this.updateAllViews();
    }

    attached({ chart, series, requestUpdate }: { chart: IChartApi; series: ISeriesApi<any>; requestUpdate: () => void }) {
        this._chart = chart;
        this._series = series;
        this.updateAllViews();
        requestUpdate();
    }

    detached() {
        this._chart = null;
        this._series = null;
    }

    updateAllViews() {
        this._paneViews.forEach(view => view.update());
    }

    paneViews() {
        return this._paneViews;
    }
}
