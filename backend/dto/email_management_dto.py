from backend.dto.base_request_dto import BaseRequestDto


class AddEmailRequest(BaseRequestDto):
    email: str


class InitiateRequest(BaseRequestDto):
    email: str


class VerifyRequest(BaseRequestDto):
    state: str
    otp: str


class OtpConfirmRequest(BaseRequestDto):
    state: str
    code: str
