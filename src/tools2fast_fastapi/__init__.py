from .models.mixins import AuditMixin, AuditTimestampMixin, IdMixin, UUIDIdMixin, TimestampMixin, NumberUniqueMixin, RevisionMixin, NumberMixin, SoftDeleteMixin
from .services import DocumentSimpleRevisionService, DocumentWithItemsRevisionService, TransactionService
from .services.soft_delete import soft_delete, restore, active_only, deleted_only
from .schemas import (
    APIResponse,
    AuthError,
    install_auth_error_handler,
    BaseSuccessResponse,
    BaseControlledErrorResponse,
    BaseUnexpectedErrorResponse,
    BasePaymentRequiredResponse,
    ErrorDetail,
    SuccessResponseMixin,
    ControlledErrorMixin,
    UnexpectedErrorMixin,
    PaymentRequiredMixin,
)
from .utils import SafeRouter
from . import schemas
from .__version__ import __version__

__all__ = [
    # Model mixins
    "AuditTimestampMixin",
    "IdMixin",
    "UUIDIdMixin",
    "TimestampMixin",
    "AuditMixin",
    "NumberUniqueMixin",
    "RevisionMixin",
    "NumberMixin",
    "SoftDeleteMixin",
    # Soft-delete functions
    "soft_delete",
    "restore",
    "active_only",
    "deleted_only",
    # Response models
    "APIResponse",
    "AuthError",
    "install_auth_error_handler",
    "BaseSuccessResponse",
    "BaseControlledErrorResponse",
    "BaseUnexpectedErrorResponse",
    "BasePaymentRequiredResponse",
    # Error detail
    "ErrorDetail",
    # Response mixins
    "SuccessResponseMixin",
    "ControlledErrorMixin",
    "UnexpectedErrorMixin",
    "PaymentRequiredMixin",
    # Utils
    "SafeRouter",
    # Services
    "DocumentSimpleRevisionService",
    "DocumentWithItemsRevisionService",
    "TransactionService",
    # Modules
    "schemas",
    "__version__",
]
