import { state } from './state.js';

export async function loadAndApplyPlugin(moduleName, displayName, type = 'primitive') {
    if (state.pluginModules.has(moduleName)) {
        alert(`${displayName} already loaded`);
        return;
    }

    try {
        // Dynamic import from plugins directory
        const module = await import('../plugins/' + moduleName + '.js');
        state.pluginModules.set(moduleName, module);

        // Apply based on type
        if (type === 'primitive') {
            // For TooltipPrimitive, VertLine, etc.
            const PrimitiveClass = module[Object.keys(module)[0]];
            const primitive = new PrimitiveClass();
            window.chartSeries.attachPrimitive(primitive);
            state.activePlugins.push({ name: moduleName, displayName: displayName, instance: primitive });
            console.log(`✅ Plugin '${displayName}' loaded and attached`);
            alert(`${displayName} enabled!`);
            updatePluginList();
        }
        else if (type === 'indicator') {
            // For moving-average, etc.
            const indicatorFn = module[Object.keys(module)[0]];
            const indicatorSeries = indicatorFn(window.chartSeries, { length: 20 });
            state.activePlugins.push({ name: moduleName, displayName: displayName, series: indicatorSeries });
            console.log(`✅ Indicator '${displayName}' loaded and applied`);
            alert(`${displayName} added!`);
            updatePluginList();
        }

    } catch (error) {
        console.error(`Failed to load ${displayName}:`, error);
        alert(`Error loading ${displayName}: ${error.message}`);
    }
}

export function updatePluginList() {
    const listDiv = document.getElementById('plugin-list');
    const countSpan = document.getElementById('plugin-count');

    if (state.activePlugins.length === 0) {
        listDiv.innerHTML = '<div style="color: #888; font-size: 12px; padding: 10px; text-align: center;">No plugins loaded</div>';
        countSpan.textContent = '0';
        return;
    }

    countSpan.textContent = state.activePlugins.length.toString();

    let html = '';
    state.activePlugins.forEach((plugin, index) => {
        html += `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px; margin: 2px 0; background: #1e222d; border-radius: 3px;">
                <span style="color: #d1d4dc; font-size: 12px;">${plugin.displayName || plugin.name}</span>
                <button onclick="removePlugin(${index})" style="background: #ef5350; color: white; border: none; padding: 2px 6px; border-radius: 2px; cursor: pointer; font-size: 10px;">✕</button>
            </div>
        `;
    });
    listDiv.innerHTML = html;
}

export function removePlugin(index) {
    if (index < 0 || index >= state.activePlugins.length) return;

    const plugin = state.activePlugins[index];

    try {
        // Remove primitive
        if (plugin.instance && plugin.instance.detach) {
            plugin.instance.detach();
        }
        // Remove indicator series
        if (plugin.series && window.chart.removeSeries) {
            window.chart.removeSeries(plugin.series);
        }

        state.activePlugins.splice(index, 1);
        state.pluginModules.delete(plugin.name);

        updatePluginList();
        console.log(`✅ Removed plugin: ${plugin.displayName || plugin.name}`);
    } catch (error) {
        console.error(`Error removing plugin:`, error);
        alert(`Error removing plugin: ${error.message}`);
    }
}

export function clearAllPlugins() {
    if (state.activePlugins.length === 0) {
        alert('No plugins to remove');
        return;
    }

    if (!confirm(`Remove all ${state.activePlugins.length} plugins?`)) {
        return;
    }

    // Remove all in reverse order
    for (let i = state.activePlugins.length - 1; i >= 0; i--) {
        const plugin = state.activePlugins[i];
        try {
            if (plugin.instance && plugin.instance.detach) {
                plugin.instance.detach();
            }
            if (plugin.series && window.chart.removeSeries) {
                window.chart.removeSeries(plugin.series);
            }
        } catch (error) {
            console.error(`Error removing ${plugin.name}:`, error);
        }
    }

    state.activePlugins = [];
    state.pluginModules.clear();
    updatePluginList();
    console.log('✅ All plugins removed');
}

export function togglePluginManager() {
    const manager = document.getElementById('plugin-manager');
    manager.style.display = manager.style.display === 'none' ? 'block' : 'none';
}
