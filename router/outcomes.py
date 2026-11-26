from enum import StrEnum


class Status(StrEnum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Outcome(StrEnum):
    DONE = "done"
    SATISFIED = "satisfied"
    FAILED = "failed"


class Stop(StrEnum):
    NONE = "none"
    ACCEPT_FAILED = "accept_failed"
    CHECKER = "checker"
    NO_CHANGE = "no_change"
    SCOPE = "scope"
    OUT_OF_TIME = "out_of_time"
    MAX_STEPS = "max_steps"
    REPEAT_GUARD = "repeat_guard"
    NO_TOOL_CALL = "no_tool_call"
    BAD_TOOL_CALL = "bad_tool_call"
    BAD_ANSWER = "bad_answer"
    MODEL_UNSUPPORTED = "model_unsupported"
    ENV_MISSING = "env_missing"
    INFRA = "infra"
    CONNECTION = "connection"
    GPU_BUSY = "gpu_busy"
    WORKSPACE_BUSY = "workspace_busy"
    ERROR = "error"


class Next(StrEnum):
    RESUME = "resume"
    RESCOPE = "rescope"
    FALLBACK = "fallback"
    FIX_ENV = "fix_env"
    RETRY_LATER = "retry_later"
    NONE = "none"


class EnvKind(StrEnum):
    VENV = "venv"
    SYSTEM_PYTHON = "system-python"
    MISSING = "missing"


NEXT = {
    Stop.NONE: Next.NONE, Stop.ACCEPT_FAILED: Next.RESUME, Stop.CHECKER: Next.RESUME,
    Stop.NO_CHANGE: Next.RESCOPE, Stop.SCOPE: Next.RESCOPE, Stop.OUT_OF_TIME: Next.RESCOPE,
    Stop.MAX_STEPS: Next.RESCOPE, Stop.REPEAT_GUARD: Next.RESCOPE, Stop.NO_TOOL_CALL: Next.RESUME,
    Stop.BAD_TOOL_CALL: Next.RESUME, Stop.BAD_ANSWER: Next.RESUME, Stop.MODEL_UNSUPPORTED: Next.FIX_ENV,
    Stop.ENV_MISSING: Next.FIX_ENV, Stop.INFRA: Next.FIX_ENV, Stop.CONNECTION: Next.RETRY_LATER,
    Stop.GPU_BUSY: Next.RETRY_LATER, Stop.WORKSPACE_BUSY: Next.RETRY_LATER, Stop.ERROR: Next.FALLBACK,
}

LEGACY_ERROR_KINDS = ("gpu_busy", "infra", "step_timeout", "request_timeout", "no_tool_call", "max_steps", "bad_answer", "no_tools", "malformed_tool_call", "error", "checker")
LEGACY_FAILURE_REASONS = ("infra", "no-tools", "connection", "timeout", "no-tool-call", "malformed-tool-call", "out-of-steps", "bad-answer", "unknown", "checker", "gpu-busy")
_ERROR_MAP = {"step_timeout": Stop.OUT_OF_TIME, "request_timeout": Stop.OUT_OF_TIME, "no_tools": Stop.MODEL_UNSUPPORTED, "malformed_tool_call": Stop.BAD_TOOL_CALL}
_REASON_MAP = {"infra": Stop.INFRA, "no-tools": Stop.MODEL_UNSUPPORTED, "connection": Stop.CONNECTION, "timeout": Stop.OUT_OF_TIME, "no-tool-call": Stop.NO_TOOL_CALL, "malformed-tool-call": Stop.BAD_TOOL_CALL, "out-of-steps": Stop.MAX_STEPS, "bad-answer": Stop.BAD_ANSWER, "checker": Stop.CHECKER, "gpu-busy": Stop.GPU_BUSY}

def stop_from_legacy(failure_reason, error_kind) -> Stop:
    if isinstance(error_kind, Stop) and error_kind is not Stop.ERROR:
        return error_kind
    if error_kind in {s.value for s in Stop if s is not Stop.ERROR}:
        return Stop(error_kind)
    mapped = _ERROR_MAP.get(error_kind)
    if mapped:
        return mapped
    if error_kind not in (None, "error"):
        return Stop.ERROR
    if isinstance(failure_reason, Stop) and failure_reason is not Stop.ERROR:
        return failure_reason
    if failure_reason in {s.value for s in Stop if s is not Stop.ERROR}:
        return Stop(failure_reason)
    return _REASON_MAP.get(failure_reason, Stop.ERROR)
