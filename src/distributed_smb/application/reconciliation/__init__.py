"""Client-side prediction, reconciliation, and shadow-copy contracts."""

from distributed_smb.application.reconciliation.noop import NoopPredictionEngine
from distributed_smb.application.reconciliation.protocol import PredictionEngineProtocol
from distributed_smb.application.reconciliation.shadow_copy import NoopShadowCopy, ShadowCopyProtocol

__all__ = [
    "PredictionEngineProtocol",
    "NoopPredictionEngine",
    "ShadowCopyProtocol",
    "NoopShadowCopy",
]
