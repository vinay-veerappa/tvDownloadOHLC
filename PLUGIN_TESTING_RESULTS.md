# Plugin Testing Results - 2025-12-04

## Test Session: Initial Plugin Testing

**Date**: 2025-12-04 09:15-09:19 PST  
**Tester**: User manual testing  
**Chart**: ES1, 1h timeframe, 20,000 bars

---

## ✅ Fully Working Plugins (5)

### Indicators
1. **Moving Average** ✅
   - Status: Working
   - Load time: Fast
   - Display: Overlay line on main chart
   - Notes: No issues

2. **Momentum** ✅
   - Status: Working
   - Load time: Fast
   - Display: Works correctly
   - Notes: No issues

3. **Average Price** ✅
   - Status: Working
   - Load time: Fast
   - Display: Works correctly
   - Console: Shows data array logs (20000 items)
   - Notes: No issues

4. **Weighted Close** ✅
   - Status: Working
   - Load time: Fast
   - Display: Works correctly
   - Notes: No issues

5. **Percent Change** ✅
   - Status: Working
   - Load time: Fast
   - Display: Works correctly
   - Notes: No issues

### Primitives
6. **Crosshair Tooltip** ✅ (tested earlier)
   - Status: Working
   - Display: Shows OHLC values on hover
   - Notes: No issues

---

## ❌ Plugins Requiring Special Initialization (2)

### 1. Correlation ❌
**Error**: `TypeError: this._secondarySeries.subscribeDataChanged is not a function`  
**Location**: `correlation.js:94:206`  
**Root Cause**: Requires a **secondary series** for correlation analysis  
**Current Behavior**: 
- Plugin loads but crashes when trying to attach
- Causes additional errors when changing timeframes
- Error: `this._secondarySeries.data is not a function`

**Required Fix**: 
- Need to pass two series objects
- Need UI to select which two instruments to correlate
- Example: Correlate ES1 vs NQ1

**Workaround**: Remove from menu until dual-series support added

---

### 2. Product ❌
**Error**: `TypeError: this._secondarySeries.subscribeDataChanged is not a function`  
**Location**: `product.js:83:206`  
**Root Cause**: Requires a **secondary series** for multiplication  
**Current Behavior**: Same as Correlation - requires two series

**Required Fix**: Same as Correlation - needs dual-series architecture

**Workaround**: Remove from menu until dual-series support added

---

## 🔧 Plugins Not Yet Tested

### Indicators
- [ ] Median Price
- [ ] Ratio (likely needs dual-series)
- [ ] Spread (likely needs dual-series)
- [ ] Sum

### Primitives
- [ ] Delta Tooltip
- [ ] Volume Profile (known to need special init)
- [ ] Session Highlighting (known to need config)
- [ ] Vertical Line
- [ ] Anchored Text
- [ ] User Price Lines
- [ ] User Price Alerts

---

## 📊 Success Rate

**Tested**: 8 plugins  
**Working**: 6 (75%)  
**Requiring Special Setup**: 2 (25%)

---

## 🎯 Recommendations

### Immediate (Phase 2a)
1. **Remove dual-series plugins from menu** (Correlation, Product, Ratio, Spread)
   - Prevents user confusion and errors
   - Can add back when dual-series support is implemented

2. **Test remaining single-series indicators**
   - Median Price, Sum
   - Verify they work like the others

3. **Test primitives**
   - Start with simple ones: Delta Tooltip, Vertical Line, Anchored Text
   - Save complex ones for later: Volume Profile, Session Highlighting

### Future (Phase 2b)
1. **Implement dual-series support**
   - Add UI to select two instruments
   - Modify loadAndApplyPlugin to accept secondary series
   - Re-enable Correlation, Product, Ratio, Spread

2. **Add configuration UI**
   - For plugins that need parameters (Volume Profile, Session Highlighting)
   - Allow users to customize indicator periods, colors, etc.

3. **Add plugin removal**
   - UI to remove loaded plugins
   - Clear button for all plugins

---

## 💡 Lessons Learned

1. **Not all plugins have same initialization pattern**
   - Single-series vs dual-series
   - Some need configuration objects

2. **Error handling works**
   - Try-catch in loadAndApplyPlugin caught the errors
   - Users got error alerts instead of silent failures

3. **Console logging helpful**
   - "✅ Indicator loaded" messages confirm success
   - Error messages pinpoint exact issue

4. **75% success rate is good for initial implementation**
   - Core system working correctly
   - Failures are due to plugin requirements, not system bugs

---

## 🐛 Known Issues

1. **Correlation plugin causes persistent errors**
   - Once loaded (even failed), causes errors on timeframe changes
   - Requires page reload to clear
   - **Workaround**: Don't load Correlation/Product until fix implemented

2. **Average Price logs data array to console**
   - Not an error, but clutters console
   - Could remove debug logging from plugin file

---

## ✅ Next Testing Session

**Goals**:
1. Test Median Price and Sum indicators
2. Test 3-4 primitive plugins
3. Verify page reload cleans up failed plugins
4. Test same plugin loading twice (should alert "already loaded")
