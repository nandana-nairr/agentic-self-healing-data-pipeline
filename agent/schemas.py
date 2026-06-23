from enum import Enum
from pydantic import BaseModel, Field


class FailureType(str, Enum):
    DUPLICATE_ORDERS = "duplicate_orders"
    NULL_ORDERS = "null_orders"
    INVALID_STATUS = "invalid_status"
    UNKNOWN = "unknown"


class RecoveryTool(str, Enum):
    REPAIR_DUPLICATE_ORDERS = "repair_duplicate_orders"
    REPAIR_NULL_ORDERS = "repair_null_orders"
    REPAIR_INVALID_STATUS = "repair_invalid_status"
    QUARANTINE_ROWS = "quarantine_rows"
    RERUN_VALIDATION = "rerun_validation"
    NONE = "none"


class RecoveryDecision(BaseModel):
    failure_type: FailureType
    selected_tool: RecoveryTool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    should_escalate: bool