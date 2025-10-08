from enum import Enum

#DEAD CODE

class CallTypeEnum(Enum):
    """Call Type Enums"""

    GET = ("GET",)
    POST = ("POST",)
    PUT = ("PUT",)
    DELETE = ("DELETE",)
    PATCH = ("PATCH",)
    HEAD = ("HEAD",)
    OPTIONS = ("OPTIONS",)
    CONNECT = ("CONNECT",)
    TRACE = "TRACE"
