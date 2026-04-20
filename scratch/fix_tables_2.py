import re

with open(r'C:\Users\vinay\tvDownloadOHLC\scripts\indicators\daily-ny-levels\DailyNYLevelsAnalytics.pine', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace table.new exactly as before, it worked fine
text = re.sub(r'table\.new\(Tables\.f_table_pos\((.*?)\),\s*(.*?),\s*(.*?),\s*bgcolor=(.*?),?\s*border_color=(.*?),?\s*border_width=(.*?)\)',
              r'Tables.f_new_table(\1, \2, \3, \4, \5, \6)', text, flags=re.DOTALL)
text = re.sub(r'table\.new\((.*?),\s*(.*?),\s*(.*?),\s*bgcolor=(.*?),?\s*border_color=(.*?),?\s*border_width=(.*?)\)',
              r'Tables.f_new_table(\1, \2, \3, \4, \5, \6)', text, flags=re.DOTALL)

# Find 'table.cell(' and parse its balanced arguments
new_text = ""
idx = 0
while idx < len(text):
    pos = text.find('table.cell(', idx)
    if pos == -1:
        new_text += text[idx:]
        break
    
    new_text += text[idx:pos]
    
    # parse arguments inside table.cell(...)
    start_args = pos + len('table.cell(')
    curr_idx = start_args
    depth = 1
    args = []
    curr_arg = ""
    
    while curr_idx < len(text) and depth > 0:
        c = text[curr_idx]
        if c == '(':
            depth += 1
            curr_arg += c
        elif c == ')':
            depth -= 1
            if depth == 0:
                args.append(curr_arg.strip())
                break
            else:
                curr_arg += c
        elif c == ',' and depth == 1:
            args.append(curr_arg.strip())
            curr_arg = ""
        else:
            curr_arg += c
            
        curr_idx += 1
        
    idx = curr_idx + 1 # move past ')'
    
    # map args
    t = args[0] if len(args) > 0 else 't'
    col = args[1] if len(args) > 1 else '0'
    row = args[2] if len(args) > 2 else '0'
    val = args[3] if len(args) > 3 else '""'
    
    bg = 'na'
    text_color = 'na'
    text_size = '"Normal"'
    col_span = '1'
    text_halign = 'text.align_center'
    
    is_header = False
    
    arg_idx = 4
    for arg in args[4:]:
        if '=' in arg and not arg.startswith('color.new(') and not arg.startswith('color('): # named param
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
        else:
            if arg_idx == 4: pass # width
            elif arg_idx == 5: pass # height
            elif arg_idx == 6:
                if arg.startswith('color'): bg = arg
            arg_idx += 1
            
        if 'header' in arg.lower() or 'header' in val.lower():
            is_header = True
            
    fname = 'Tables.f_draw_header_cell' if is_header else 'Tables.f_draw_value_cell'
    new_text += f"{fname}({t}, {col}, {row}, {val}, {bg}, {text_color}, {text_size}, {col_span}, {text_halign})"

with open(r'C:\Users\vinay\tvDownloadOHLC\scripts\indicators\daily-ny-levels\DailyNYLevelsAnalytics.pine', 'w', encoding='utf-8') as f:
    f.write(new_text)

print("Replacement complete.")
