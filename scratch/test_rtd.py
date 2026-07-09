import sys
import time
import pythoncom
from comtypes import COMObject
from ctypes.wintypes import VARIANT_BOOL
from comtypes.automation import VARIANT

sys.path.append(r'C:\Users\vinay\tvDownloadOHLC')
from scripts.streaming.options.tos_rtd.interfaces import IRTDUpdateEvent, IRtdServer
from scripts.streaming.options.tos_rtd.settings import SETTINGS
from comtypes.client import CreateObject

class MinimalRTDClient(COMObject):
    _com_interfaces_ = [IRTDUpdateEvent]

    def UpdateNotify(self) -> int:
        print(">>> UpdateNotify called!")
        return 1

    def HeartbeatInterval(self, *args) -> int:
        return 1
        
    def Disconnect(self):
        print(">>> Disconnect called!")

import threading

def run_rtd():
    pythoncom.CoInitialize()
    client = MinimalRTDClient()
    
    # Force creation of thread message queue
    pythoncom.PumpWaitingMessages()

    server = CreateObject(SETTINGS.progid, interface=IRtdServer)
    print("Server Start:", server.ServerStart(client))

    # Try subscribing
    strings_c_array = (VARIANT * 2)()
    strings_c_array[0].value = "LAST"
    strings_c_array[1].value = "/ES:XCME"

    try:
        topic_id = 1
        get_new_values = VARIANT_BOOL(True)
        res = server.ConnectData(topic_id, strings_c_array, get_new_values)
        print("ConnectData (C array) result:", res)
    except Exception as e:
        print("ConnectData (C array) error:", e)

    # Now wait for events
    for i in range(10):
        pythoncom.PumpWaitingMessages()
        time.sleep(0.5)
        try:
            res = server.RefreshData()
            print("RefreshData:", res)
        except Exception as e:
            print("RefreshData error:", e)

    server.ServerTerminate()
    pythoncom.CoUninitialize()

t = threading.Thread(target=run_rtd)
t.start()
t.join()
