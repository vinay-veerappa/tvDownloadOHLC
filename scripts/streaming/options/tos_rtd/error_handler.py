"""
Error handling and connection state management for RTD client.

Ported from: 2187Nick/tos-streamlit-dashboard (futures branch)
Source: src/core/error_handler.py

Consolidated into a single module for our codebase — removes the
src/core dependency chain.
"""
from __future__ import annotations

import logging
from enum import Enum, auto
from functools import wraps
from typing import List, Type

import comtypes

log = logging.getLogger(__name__)


class RTDConnectionState(Enum):
    """Connection states for the RTD update event handler."""

    DISCONNECTED = auto()
    CONNECTED = auto()
    CONNECTING = auto()
    DISCONNECTING = auto()


class RTDError(Exception):
    """Base exception for all RTD-related errors."""

    def __init__(self, message: str, *args):
        super().__init__(message, *args)
        log.error("%s: %s", self.__class__.__name__, message)


class RTDUpdateError(RTDError):
    """Errors related to RTD update processing."""


class RTDConnectionError(RTDError):
    """Errors related to RTD connection state changes."""


class RTDHeartbeatError(RTDError):
    """Errors related to RTD heartbeat operations."""


class RTDServerError(RTDError):
    """Errors related to RTD server operations."""


class RTDClientError(RTDError):
    """Errors related to RTD client operations."""


class RTDConfigError(RTDError):
    """Errors related to RTD configuration."""


def handle_com_error(error_class: Type[RTDError] = RTDError):
    """Decorator: catch COMError and re-raise as the specified RTD error."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except comtypes.COMError as e:
                hresult, text, details = e.args
                error_msg = f"COM error in {func.__name__}: [0x{hresult:08x}] {text}"
                log.error(error_msg, exc_info=True)
                raise error_class(error_msg) from e
            except RTDError:
                raise
            except Exception as e:
                error_msg = f"Unexpected error in {func.__name__}: {e}"
                log.error(error_msg, exc_info=True)
                raise error_class(error_msg) from e

        return wrapper

    return decorator


def validate_connection_state(expected_states: List[RTDConnectionState]):
    """Decorator: validate RTD connection state before method execution."""

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            current_state = getattr(self, "_state", RTDConnectionState.DISCONNECTED)
            if current_state in expected_states:
                return func(self, *args, **kwargs)

            # Special cases
            if func.__name__ == "heartbeat" and current_state == RTDConnectionState.DISCONNECTED:
                log.debug("Skipping heartbeat in %s state", current_state)
                return None
            if func.__name__ == "Disconnect" and current_state in {
                RTDConnectionState.DISCONNECTED,
                RTDConnectionState.DISCONNECTING,
            }:
                log.debug("Skipping Disconnect in %s state", current_state)
                return None
            if current_state == RTDConnectionState.DISCONNECTING:
                log.warning("Cannot call %s during shutdown", func.__name__)
                return None

            raise RTDConnectionError(
                f"Invalid state for {func.__name__}: "
                f"Expected {[s.name for s in expected_states]}, "
                f"but was {current_state.name}"
            )

        return wrapper

    return decorator


def log_method_call(log_level: str = "DEBUG"):
    """Decorator: log method entry/exit."""

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            method_logger = getattr(self, "logger", log)
            log_func = getattr(method_logger, log_level.lower(), method_logger.debug)

            arg_str = ", ".join(
                [f"{a}" for a in args] + [f"{k}={v}" for k, v in kwargs.items()]
            )
            log_func("Entering %s(%s)", func.__name__, arg_str)

            try:
                result = func(self, *args, **kwargs)
                log_func("Exiting %s", func.__name__)
                return result
            except Exception as e:
                method_logger.error("Error in %s: %s", func.__name__, e)
                raise

        return wrapper

    return decorator