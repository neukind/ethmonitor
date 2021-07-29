from enum import Enum


class RequestTypes(Enum):
    ADD = 1
    UP = 2
    DEL = 3
    GET = 4


class ListUpdate(Enum):
    ADD = 1
    DEL = 2
    BOTH = 3


class ValidatorStatus(Enum):
    UNKNOWN_STATUS = 0
    DEPOSITED = 1
    PENDING = 2
    ACTIVE = 3
    EXITING = 4
    SLASHING = 5
    EXITED = 6
    INVALID = 7
    PARTIALLY_DEPOSITED = 8
