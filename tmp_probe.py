import urllib.request, json

TOKEN='d0b837223cab4653'
url='http://127.0.0.1:7890/api/dev/reflect'
xml = '<HorizontalLine xmlns="">'
xml += '<StartAnchor><Price>30000</Price></StartAnchor>'
xml += '<Stroke><Brush>#FFFF0000</Brush><Width>2</Width></Stroke>'
xml += '<Tag>h1</Tag>'
xml += '</HorizontalLine>'
body=json.dumps({
  'ui':True,
  'ops':[
    {'op':'new','type':'NinjaTrader.NinjaScript.DrawingTools.HorizontalLine','args':[]},
    {'op':'invoke','target':{'$result':'0'},'method':'GetType','args':[]},
    {'op':'invoke','target':{'$result':'1'},'method':'GetProperties','args':[{'$enum':'System.Reflection.BindingFlags.Instance'},{'$enum':'System.Reflection.BindingFlags.Public'},{'$enum':'System.Reflection.BindingFlags.NonPublic'}]},
    {'op':'getProp','target':{'$result':'2'},'member':'Length'},
    {'op':'invoke','target':{'$result':'1'},'method':'GetFields','args':[{'$enum':'System.Reflection.BindingFlags.Instance'},{'$enum':'System.Reflection.BindingFlags.Public'},{'$enum':'System.Reflection.BindingFlags.NonPublic'}]},
    {'op':'getProp','target':{'$result':'4'},'member':'Length'},
    {'op':'invoke','target':{'$result':'1'},'method':'get_BaseType','args':[]},
    {'op':'invoke','target':{'$result':'6'},'method':'GetProperties','args':[{'$enum':'System.Reflection.BindingFlags.Instance'},{'$enum':'System.Reflection.BindingFlags.Public'},{'$enum':'System.Reflection.BindingFlags.NonPublic'}]},
    {'op':'getProp','target':{'$result':'7'},'member':'Length'},
    {'op':'invoke','target':{'$result':'6'},'method':'GetFields','args':[{'$enum':'System.Reflection.BindingFlags.Instance'},{'$enum':'System.Reflection.BindingFlags.Public'},{'$enum':'System.Reflection.BindingFlags.NonPublic'}]},
    {'op':'getProp','target':{'$result':'9'},'member':'Length'}
  ]
}).encode()
req=urllib.request.Request(url, data=body, headers={'Host':'localhost','Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'})
try:
    resp=urllib.request.urlopen(req, timeout=15)
    print(resp.read().decode())
except urllib.error.HTTPError as e:
    print(e.code, e.read().decode())
