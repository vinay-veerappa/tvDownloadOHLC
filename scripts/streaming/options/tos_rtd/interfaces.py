"""
COM interface definitions for TOS RTD server.

Ported from: 2187Nick/tos-streamlit-dashboard (futures branch)
Source: src/rtd/interfaces.py

Defines the IRtdServer and IRTDUpdateEvent COM dispatch interfaces
using comtypes, matching the ThinkorSwim RTD COM server contract.
"""
from __future__ import annotations

from ctypes import HRESULT, POINTER, c_int
from ctypes.wintypes import VARIANT_BOOL

from comtypes import COMMETHOD, GUID, dispid
from comtypes.automation import VARIANT, IDispatch, _midlSAFEARRAY

from .settings import SETTINGS

# GUIDs
GUID_IRtdServer = GUID(SETTINGS.server_guid)
GUID_IRTDUpdateEvent = GUID(SETTINGS.update_event_guid)
LIBID_RTDServerLib = GUID(SETTINGS.typelib_guid)


class IRTDUpdateEvent(IDispatch):
    """Callback interface — TOS RTD calls this when new data is available."""

    _case_insensitive_ = True
    _iid_ = GUID_IRTDUpdateEvent
    _idlflags_ = ["dual", "oleautomation"]
    _methods_ = [
        COMMETHOD([dispid(10)], HRESULT, "UpdateNotify"),
        COMMETHOD(
            [dispid(11), "propget"],
            HRESULT,
            "HeartbeatInterval",
            (["out", "retval"], POINTER(c_int), "plRetVal"),
        ),
        COMMETHOD(
            [dispid(11), "propput"],
            HRESULT,
            "HeartbeatInterval",
            (["in"], c_int, "plRetVal"),
        ),
        COMMETHOD([dispid(12)], HRESULT, "Disconnect"),
    ]


class IRtdServer(IDispatch):
    """Main RTD server interface — subscribe/refresh/unsubscribe topics."""

    _case_insensitive_ = True
    _iid_ = GUID_IRtdServer
    _idlflags_ = ["dual", "oleautomation"]
    _methods_ = [
        COMMETHOD(
            [dispid(10)],
            HRESULT,
            "ServerStart",
            (["in"], POINTER(IRTDUpdateEvent), "CallbackObject"),
            (["out", "retval"], POINTER(c_int), "pfRes"),
        ),
        COMMETHOD(
            [dispid(11)],
            HRESULT,
            "ConnectData",
            (["in"], c_int, "TopicID"),
            (["in"], POINTER(_midlSAFEARRAY(VARIANT)), "Strings"),
            (["in", "out"], POINTER(VARIANT_BOOL), "GetNewValues"),
            (["out", "retval"], POINTER(VARIANT), "pvarOut")),
        COMMETHOD(
            [dispid(12)],
            HRESULT,
            "RefreshData",
            (["in", "out"], POINTER(c_int), "TopicCount"),
            (["out", "retval"], POINTER(_midlSAFEARRAY(VARIANT)), "parrayOut")),
        COMMETHOD([dispid(13)], HRESULT, "DisconnectData", (["in"], c_int, "TopicID")),
        COMMETHOD(
            [dispid(14)], HRESULT, "Heartbeat", (["out", "retval"], POINTER(c_int), "pfRes")
        ),
        COMMETHOD([dispid(15)], HRESULT, "ServerTerminate"),
    ]


class Library:
    """Type library reference for comtypes registration."""

    name = "RTDServerLib"
    _reg_typelib_ = (LIBID_RTDServerLib, 1, 0)


__all__ = ["IRTDUpdateEvent", "IRtdServer", "Library"]