import re

file_path = r'c:\Users\vinay\tvDownloadOHLC\scripts\indicators\htf_ema_analysis\HTF_EMA_Analysis.pine'
with open(file_path, 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Update variable definitions
replacements = {
    'var int weekStartIdx = na': 'var int weekStartTime = na',
    'var int currMonthStartIdx = na': 'var int currMonthStartTime = na',
    'var int sundayBoxStart = na': 'var int sundayBoxStartTime = na',
    'var int sundayBoxRight = na': 'var int sundayBoxEndTime = na',
    'var int tuesdayBoxStart = na': 'var int tuesdayBoxStartTime = na',
    'var int tuesdayBoxRight = na': 'var int tuesdayBoxEndTime = na',
    'var int yestStartIdx = na': 'var int yestStartTime = na',

    'currMonthStartIdx := bar_index': 'currMonthStartTime := time',
    'weekStartIdx := bar_index': 'weekStartTime := time',
    'yestStartIdx := bar_index': 'yestStartTime := time',

    'sundayBoxStart := bar_index': 'sundayBoxStartTime := time',
    'tuesdayBoxStart := bar_index': 'tuesdayBoxStartTime := time',

    'sundayBoxRight := bar_index': 'sundayBoxEndTime := time_close',
    'tuesdayBoxRight := bar_index': 'tuesdayBoxEndTime := time_close',

    'f_update_segment_line(line ln, bool show, float y, int x1, int x2, color c, int w, string style) =>': 'f_update_segment_line(line ln, bool show, float y, int t1, int t2, color c, int w, string style) =>',
    'if show and not na(y) and x1 >= 0 and x2 >= x1': 'if show and not na(y) and not na(t1) and not na(t2)',
    'out := line.new(x1, y, x2, y, xloc=xloc.bar_index, extend=extend.none, color=c, width=w, style=f_line_style(style))': 'out := line.new(t1, y, t2, y, xloc=xloc.bar_time, extend=extend.none, color=c, width=w, style=f_line_style(style))',
    'line.set_x1(out, x1)': 'line.set_x1(out, t1)',
    'line.set_x2(out, x2)': 'line.set_x2(out, t2)',

    'currMonthStartIdx, bar_index + 5': 'currMonthStartTime, time_close + (time_close - time) * 5',

    'if i_showEmaZones and not na(weeklyEma) and not na(weekStartIdx)': 'if i_showEmaZones and not na(weeklyEma) and not na(weekStartTime)',
    'int zRight = bar_index + 5': 'int zEndTime = time_close + (time_close - time) * 5',
    'box.set_left(upperZoneBox, weekStartIdx)': 'box.set_left(upperZoneBox, weekStartTime)',
    'box.set_right(upperZoneBox, zRight)': 'box.set_right(upperZoneBox, zEndTime)',
    'box.set_left(lowerZoneBox, weekStartIdx)': 'box.set_left(lowerZoneBox, weekStartTime)',
    'box.set_right(lowerZoneBox, zRight)': 'box.set_right(lowerZoneBox, zEndTime)'
}

for old, new in replacements.items():
    code = code.replace(old, new)


# Multi-line or complex replacements:
# Upper zone box
old_upper_box = 'upperZoneBox := box.new(weekStartIdx, upperZoneHi, zRight, upperZoneLo, border_color=color.new(i_cUpper, 60), bgcolor=color.new(i_cUpper, i_zoneFillOpacity), border_width=1)'
new_upper_box = 'upperZoneBox := box.new(weekStartTime, upperZoneHi, zEndTime, upperZoneLo, xloc=xloc.bar_time, border_color=color.new(i_cUpper, 60), bgcolor=color.new(i_cUpper, i_zoneFillOpacity), border_width=1)'
code = code.replace(old_upper_box, new_upper_box)

old_lower_box = 'lowerZoneBox := box.new(weekStartIdx, lowerZoneHi, zRight, lowerZoneLo, border_color=color.new(i_cLower, 60), bgcolor=color.new(i_cLower, i_zoneFillOpacity), border_width=1)'
new_lower_box = 'lowerZoneBox := box.new(weekStartTime, lowerZoneHi, zEndTime, lowerZoneLo, xloc=xloc.bar_time, border_color=color.new(i_cLower, 60), bgcolor=color.new(i_cLower, i_zoneFillOpacity), border_width=1)'
code = code.replace(old_lower_box, new_lower_box)

# Sunday box
old_s_right = 'int sRight = math.max(nz(sundayBoxRight, sundayBoxStart), sundayBoxStart + 1)'
new_s_right = 'int sEndTime = nz(sundayBoxEndTime, time_close)'
code = code.replace(old_s_right, new_s_right)

old_sunday_box = 'sundayBox := box.new(sundayBoxStart, sundayHigh, sRight, sundayLow, border_color=color.new(i_cSunday, 0), bgcolor=color.new(i_cSunday, 85), border_width=1, text="Sunday", text_color=i_cSunday, text_size=f_table_size(i_allLevelsTableSize), text_halign=text.align_right, text_valign=text.align_center, text_font_family=font.family_monospace)'
new_sunday_box = 'sundayBox := box.new(sundayBoxStartTime, sundayHigh, sEndTime, sundayLow, xloc=xloc.bar_time, border_color=color.new(i_cSunday, 0), bgcolor=color.new(i_cSunday, 85), border_width=1, text="Sunday", text_color=i_cSunday, text_size=f_table_size(i_allLevelsTableSize), text_halign=text.align_right, text_valign=text.align_center, text_font_family=font.family_monospace)'
code = code.replace(old_sunday_box, new_sunday_box)

code = code.replace('box.set_left(sundayBox, sundayBoxStart)', 'box.set_left(sundayBox, sundayBoxStartTime)')
code = code.replace('box.set_right(sundayBox, sRight)', 'box.set_right(sundayBox, sEndTime)')


# Tuesday box
old_t_right = 'int tRight = math.max(nz(tuesdayBoxRight, tuesdayBoxStart), tuesdayBoxStart + 1)'
new_t_right = 'int tEndTime = nz(tuesdayBoxEndTime, time_close)'
code = code.replace(old_t_right, new_t_right)

old_tuesday_box = 'tuesdayBox := box.new(tuesdayBoxStart, tuesdayHigh, tRight, tuesdayLow, border_color=color.new(i_cTuesday, 0), bgcolor=color.new(i_cTuesday, 85), border_width=1, text="Tuesday", text_color=i_cTuesday, text_size=f_table_size(i_allLevelsTableSize), text_halign=text.align_right, text_valign=text.align_center, text_font_family=font.family_monospace)'
new_tuesday_box = 'tuesdayBox := box.new(tuesdayBoxStartTime, tuesdayHigh, tEndTime, tuesdayLow, xloc=xloc.bar_time, border_color=color.new(i_cTuesday, 0), bgcolor=color.new(i_cTuesday, 85), border_width=1, text="Tuesday", text_color=i_cTuesday, text_size=f_table_size(i_allLevelsTableSize), text_halign=text.align_right, text_valign=text.align_center, text_font_family=font.family_monospace)'
code = code.replace(old_tuesday_box, new_tuesday_box)

code = code.replace('box.set_left(tuesdayBox, tuesdayBoxStart)', 'box.set_left(tuesdayBox, tuesdayBoxStartTime)')
code = code.replace('box.set_right(tuesdayBox, tRight)', 'box.set_right(tuesdayBox, tEndTime)')


with open(file_path, 'w', encoding='utf-8') as f:
    f.write(code)

print("Refactoring complete.")
