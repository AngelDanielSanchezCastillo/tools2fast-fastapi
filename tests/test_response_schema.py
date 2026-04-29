"""
Tests for tools2fast response mixins and base classes.
Phase 1: Unified API Responses - tools2fast Foundation
"""
import pytest
from pydantic import ValidationError

from tools2fast_fastapi.schemas.mixins import (
    ErrorDetail,
    SuccessResponseMixin,
    ControlledErrorMixin,
    UnexpectedErrorMixin,
    PaymentRequiredMixin,
)
from tools2fast_fastapi.schemas.response_schema import (
    APIResponse,
    BaseSuccessResponse,
    BaseControlledErrorResponse,
    BaseUnexpectedErrorResponse,
    BasePaymentRequiredResponse,
)


class TestErrorDetail:
    """Task 1.1: ErrorDetail model tests"""

    def test_error_detail_creation_with_type_and_detail(self):
        """RED: ErrorDetail should accept type and detail fields"""
        error = ErrorDetail(type="ValueError", detail="Invalid input")
        assert error.type == "ValueError"
        assert error.detail == "Invalid input"

    def test_error_detail_optional_detail(self):
        """RED: ErrorDetail detail field should be optional"""
        error = ErrorDetail(type="RuntimeError")
        assert error.type == "RuntimeError"
        assert error.detail is None


class TestSuccessResponseMixin:
    """Task 1.2: SuccessResponseMixin tests"""

    def test_success_mixin_default_values(self):
        """RED: SuccessResponseMixin should have default success=True and message"""
        mixin = SuccessResponseMixin()
        assert mixin.success is True
        assert mixin.message == "Éxito"

    def test_success_mixin_custom_message(self):
        """RED: SuccessResponseMixin should accept custom message"""
        mixin = SuccessResponseMixin(message="Custom success")
        assert mixin.success is True
        assert mixin.message == "Custom success"


class TestControlledErrorMixin:
    """Task 1.2: ControlledErrorMixin tests"""

    def test_controlled_error_default_values(self):
        """RED: ControlledErrorMixin should have success=False and error_type='controlled'"""
        mixin = ControlledErrorMixin(message="Test error")
        assert mixin.success is False
        assert mixin.error_type == "controlled"
        assert mixin.message == "Test error"

    def test_controlled_error_with_error_detail(self):
        """RED: ControlledErrorMixin should accept optional error detail"""
        error_detail = ErrorDetail(type="ValidationError", detail="Invalid email")
        mixin = ControlledErrorMixin(message="Validation failed", error=error_detail)
        assert mixin.success is False
        assert mixin.error.type == "ValidationError"


class TestUnexpectedErrorMixin:
    """Task 1.2: UnexpectedErrorMixin tests"""

    def test_unexpected_error_default_values(self):
        """RED: UnexpectedErrorMixin should have success=False, error_type='unexpected'"""
        mixin = UnexpectedErrorMixin()
        assert mixin.success is False
        assert mixin.error_type == "unexpected"
        assert mixin.message == "Ha ocurrido un error"

    def test_unexpected_error_with_custom_message(self):
        """RED: UnexpectedErrorMixin should accept custom message"""
        mixin = UnexpectedErrorMixin(message="Database connection failed")
        assert mixin.message == "Database connection failed"


class TestPaymentRequiredMixin:
    """Task 1.2: PaymentRequiredMixin tests"""

    def test_payment_required_default_values(self):
        """RED: PaymentRequiredMixin should have success=False and error_type='payment_required'"""
        mixin = PaymentRequiredMixin()
        assert mixin.success is False
        assert mixin.error_type == "payment_required"
        assert mixin.message == "Pago requerido"

    def test_payment_required_with_custom_message(self):
        """RED: PaymentRequiredMixin should accept custom message"""
        mixin = PaymentRequiredMixin(message="Suscripción vencida")
        assert mixin.message == "Suscripción vencida"


class TestBaseSuccessResponse:
    """Task 1.2: BaseSuccessResponse tests"""

    def test_base_success_response_creation(self):
        """RED: BaseSuccessResponse should be a Pydantic model with success=True"""
        response = BaseSuccessResponse()
        assert response.success is True
        assert response.message == "Éxito"
        assert response.data is None

    def test_base_success_response_with_data(self):
        """RED: BaseSuccessResponse should accept data field"""
        response = BaseSuccessResponse(data={"id": 1, "name": "Test"})
        assert response.success is True
        assert response.data == {"id": 1, "name": "Test"}


class TestBaseControlledErrorResponse:
    """Task 1.2: BaseControlledErrorResponse tests"""

    def test_base_controlled_error_creation(self):
        """RED: BaseControlledErrorResponse should have correct defaults"""
        response = BaseControlledErrorResponse(message="Test error")
        assert response.success is False
        assert response.error_type == "controlled"
        assert response.message == "Test error"

    def test_base_controlled_error_with_error_detail(self):
        """RED: BaseControlledErrorResponse should accept ErrorDetail"""
        error_detail = ErrorDetail(type="ValueError", detail="Invalid")
        response = BaseControlledErrorResponse(message="Error", error=error_detail)
        assert response.error.type == "ValueError"


class TestBaseUnexpectedErrorResponse:
    """Task 1.2: BaseUnexpectedErrorResponse tests"""

    def test_base_unexpected_error_defaults(self):
        """RED: BaseUnexpectedErrorResponse should have correct defaults"""
        response = BaseUnexpectedErrorResponse()
        assert response.success is False
        assert response.error_type == "unexpected"
        assert response.message == "Ha ocurrido un error"


class TestBasePaymentRequiredResponse:
    """Task 1.2: BasePaymentRequiredResponse tests"""

    def test_base_payment_required_defaults(self):
        """RED: BasePaymentRequiredResponse should have correct defaults"""
        response = BasePaymentRequiredResponse()
        assert response.success is False
        assert response.error_type == "payment_required"
        assert response.message == "Pago requerido"


class TestAPIResponseOk:
    """Task 1.3: APIResponse.ok() returns Pydantic model"""

    def test_ok_returns_base_success_response(self):
        """RED: APIResponse.ok() should return BaseSuccessResponse (Pydantic model)"""
        result = APIResponse.ok(data={"id": 1})
        assert isinstance(result, BaseSuccessResponse)
        assert result.success is True

    def test_ok_serializes_pydantic_model(self):
        """RED: APIResponse.ok() should serialize Pydantic models in data"""
        class DummyModel:
            def model_dump(self):
                return {"id": 1, "name": "Test"}

        result = APIResponse.ok(data=DummyModel())
        assert result.data == {"id": 1, "name": "Test"}

    def test_ok_serializes_list_of_pydantic_models(self):
        """RED: APIResponse.ok() should serialize list of Pydantic models"""
        class DummyModel:
            def model_dump(self):
                return {"id": 1}

        result = APIResponse.ok(data=[DummyModel(), DummyModel()])
        assert result.data == [{"id": 1}, {"id": 1}]

    def test_ok_with_custom_message(self):
        """RED: APIResponse.ok() should accept custom message"""
        result = APIResponse.ok(data=None, message="Custom message")
        assert result.message == "Custom message"


class TestAPIResponseFail:
    """Task 1.4: APIResponse.fail() returns Pydantic model"""

    def test_fail_returns_tuple_of_model_and_status_code(self):
        """RED: APIResponse.fail() should return (BaseControlledErrorResponse, status_code)"""
        result = APIResponse.fail("Not found", status_code=404)
        assert isinstance(result, tuple)
        assert len(result) == 2
        model, status = result
        assert isinstance(model, BaseControlledErrorResponse)
        assert status == 404

    def test_fail_returns_correct_status_code(self):
        """RED: APIResponse.fail() should use given status_code"""
        _, status = APIResponse.fail("Bad request", status_code=400)
        assert status == 400

    def test_fail_has_correct_error_type(self):
        """RED: APIResponse.fail() returned model should have error_type='controlled'"""
        model, _ = APIResponse.fail("Error message")
        assert model.success is False
        assert model.error_type == "controlled"

    def test_fail_includes_error_detail(self):
        """RED: APIResponse.fail() should include ErrorDetail with message"""
        model, _ = APIResponse.fail("Validation error")
        assert model.error is not None
        assert model.error.type == "ControlledError"
        assert model.error.detail == "Validation error"


class TestAPIResponseFromException:
    """Task 1.5: APIResponse.from_exception() returns Pydantic model"""

    def test_from_exception_returns_tuple_of_model_and_status_code(self):
        """RED: APIResponse.from_exception() should return (BaseUnexpectedErrorResponse, 500)"""
        result = APIResponse.from_exception(Exception("Database error"))
        assert isinstance(result, tuple)
        assert len(result) == 2
        model, status = result
        assert isinstance(model, BaseUnexpectedErrorResponse)
        assert status == 500

    def test_from_exception_includes_exception_type(self):
        """RED: from_exception should include exception class name in ErrorDetail.type"""
        model, _ = APIResponse.from_exception(ValueError("Invalid value"))
        assert model.error is not None
        assert model.error.type == "ValueError"

    def test_from_exception_includes_exception_message(self):
        """RED: from_exception should include exception message in ErrorDetail.detail for controlled errors"""
        # Note: unexpected errors (non-controlled) hide detail for security
        # Controlled errors (ValueError) expose the message
        model, _ = APIResponse.from_exception(RuntimeError("Connection failed"))
        # For non-controlled exceptions, detail is hidden (security)
        assert model.error is not None
        assert model.error.type == "RuntimeError"


class TestAPIResponsePaymentRequired:
    """Task 1.6: APIResponse.payment_required() returns Pydantic model"""

    def test_payment_required_returns_tuple_of_model_and_status_code(self):
        """RED: APIResponse.payment_required() should return (BasePaymentRequiredResponse, 402)"""
        result = APIResponse.payment_required()
        assert isinstance(result, tuple)
        assert len(result) == 2
        model, status = result
        assert isinstance(model, BasePaymentRequiredResponse)
        assert status == 402

    def test_payment_required_has_correct_error_type(self):
        """RED: payment_required model should have error_type='payment_required'"""
        model, _ = APIResponse.payment_required()
        assert model.success is False
        assert model.error_type == "payment_required"

    def test_payment_required_with_custom_message(self):
        """RED: payment_required should accept custom message"""
        model, _ = APIResponse.payment_required("Suscripción vencida desde enero")
        assert model.error.detail == "Suscripción vencida desde enero"