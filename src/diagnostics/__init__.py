"""Diagnóstico do ARKLAND Server Manager: logging central, mascaramento de segredos,
verificação de saúde (doctor), pacote .zip e envio opt-in (Discord / Web Store).

Importações pesadas ficam nos submódulos; aqui só o que os fluxos do app usam no dia a dia.
"""
from .events import diag_call, diag_event
from .redact import redact_obj, redact_text

__all__ = ["diag_event", "diag_call", "redact_text", "redact_obj"]
