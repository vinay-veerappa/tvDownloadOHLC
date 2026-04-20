import re

with open(r'C:\Users\vinay\tvDownloadOHLC\scripts\indicators\daily-ny-levels\DailyNYLevelsAnalytics.pine', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace table.new
text = re.sub(r'table\.new\(Tables\.f_table_pos\((.*?)\),\s*(.*?),\s*(.*?),\s*bgcolor=(.*?),?\s*border_color=(.*?),?\s*border_width=(.*?)\)',
              r'Tables.f_new_table(\1, \2, \3, \4, \5, \6)', text, flags=re.DOTALL)
text = re.sub(r'table\.new\((.*?),\s*(.*?),\s*(.*?),\s*bgcolor=(.*?),?\s*border_color=(.*?),?\s*border_width=(.*?)\)',
              r'Tables.f_new_table(\1, \2, \3, \4, \5, \6)', text, flags=re.DOTALL)

# This will just identify table.cell loops. We can't use simple regex for all table.cells because they have varied params.
# We will use f_draw_header_cell / f_draw_value_cell from PineDrawingTables!
# Notice: f_draw_value_cell(table t, int col, int row, string text_value, color bg, color text_color, string text_size, int col_span = 1, string text_halign = text.align_center)
# The old code:
# table.cell(t, 0, r, "? " + sp.name + " ?", 0, 0, color.new(header_bg, 80), col_span=2, text_color=header_txt, text_size=size.small)
# Actually, the 0, 0 are width and height. And color is bgcolor in reality but they put it positionally and might have caused bugs or Pine accepts it.
# We will just write a python function to parse table.cell arguments and map them to Tables.f_draw_value_cell or f_draw_header_cell.
def replace_cell(m):
    args_str = m.group(1)
    # Split args carefully by commas not inside parens
    parts = []
    curr = ''
    depth = 0
    for char in args_str:
        if char == '(': depth += 1
        elif char == ')': depth -= 1
        elif char == ',' and depth == 0:
            parts.append(curr.strip())
            curr = ''
            continue
        curr += char
    parts.append(curr.strip())
    
    t = parts[0]
    col = parts[1]
    row = parts[2]
    val = parts[3]
    
    bg = 'na'
    text_color = 'na'
    text_size = '"Normal"'
    col_span = '1'
    text_halign = 'text.align_center'
    
    # Analyze remaining args
    is_header = False
    idx = 4
    for arg in parts[4:]:
        if '=' in arg and not arg.startswith('color.new') and not arg.startswith('color('): # Named argument
            k, v = arg.split('=', 1)
            k = k.strip()
            v = v.strip()
            if k == 'bgcolor': bg = v
            elif k == 'text_color': text_color = v
            elif k == 'text_size':
                if v == 'size.tiny': text_size = '"Tiny"'
                elif v == 'size.small': text_size = '"Small"'
                elif v == 'size.normal': text_size = '"Normal"'
                elif v == 'size.large': text_size = '"Large"'
                elif v == 'size.huge': text_size = '"Huge"'
                else: text_size = v
            elif k == 'col_span': col_span = v
            elif k == 'text_halign': text_halign = v
        else: # Positional argument 
            if idx == 4: # width
                pass
            elif idx == 5: # height
                pass
            elif idx == 6: # text_color
                if arg.startswith('color'):
                    bg = arg # often they intended this as bgcolor if they pass text_color later
            idx += 1
            
        if 'header' in arg.lower():
            is_header = True
            
    # Now output
    fname = 'Tables.f_draw_header_cell' if is_header else 'Tables.f_draw_value_cell'
    return f"{fname}({t}, {col}, {row}, {val}, {bg}, {text_color}, {text_size}, {col_span}, {text_halign})"

text = re.sub(r'table\.cell\((.*?)\)', replace_cell, text)

with open(r'C:\Users\vinay\tvDownloadOHLC\scripts\indicators\daily-ny-levels\DailyNYLevelsAnalytics.pine', 'w', encoding='utf-8') as f:
    f.write(text)

print("Replacement complete.")
