"""
KYC Router — Verificação de Identidade

Fluxo:
  1. POST /api/kyc/submit  — usuário inicia o processo de verificação
  2. Provider externo valida biometria + documento
  3. POST /api/kyc/webhook — provider notifica resultado via webhook
  4. user.verified = True (APPROVED) ou KycRequest.status = REJECTED

Prevenção de conta dupla:
  - document (CPF/CNPJ) é UNIQUE na tabela users — impossível registrar o mesmo doc
  - KYC com biometria garante que doc + rosto pertencem à mesma pessoa
  - Uma tentativa ativa de KYC por usuário (constraint uq_kyc_one_per_user)

Mock mode (MOCK_KYC=true):
  - Auto-aprova qualquer submissão imediatamente (uso em dev/testes)
"""

import hashlib
import hmac
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from auth import get_current_user
from models.models import User, KycRequest
from models.enums import KycStatus
from config import settings
from pydantic import BaseModel

kyc_router = APIRouter(prefix="/kyc", tags=["kyc"])


# ─── Schemas locais ────────────────────────────────────────────────────────────

class KycSubmitRequest(BaseModel):
    """
    Dados enviados pelo cliente para iniciar a verificação.
    Em produção, o frontend coleta selfie + foto do documento via SDK do provider
    e envia os tokens/referências gerados, não os arquivos em si.
    """
    provider: str = "mock"
    selfie_token: str | None = None
    document_front_token: str | None = None
    document_back_token: str | None = None


class KycStatusResponse(BaseModel):
    id: str
    user_id: str
    document: str
    status: KycStatus
    provider: str | None
    provider_request_id: str | None
    rejection_reason: str | None
    submitted_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class KycWebhookPayload(BaseModel):
    """
    Payload enviado pelo provider KYC via webhook.
    O formato exato varia por provider — adaptar conforme contrato.
    """
    request_id: str
    status: str
    rejection_reason: str | None = None


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@kyc_router.post("/submit", response_model=KycStatusResponse, status_code=201)
async def submit_kyc(
    body: KycSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Inicia o processo de KYC para o usuário autenticado.
    Aceita apenas uma solicitação ativa por usuário.
    """
    if current_user.verified:
        raise HTTPException(status_code=400, detail="Usuário já verificado")

    existing = await db.execute(
        select(KycRequest).where(KycRequest.user_id == current_user.id)
    )
    existing_req = existing.scalar_one_or_none()

    if existing_req:
        if existing_req.status in (KycStatus.PENDING, KycStatus.IN_REVIEW):
            raise HTTPException(
                status_code=400,
                detail=f"Já existe uma solicitação de KYC em andamento (status: {existing_req.status})"
            )
        if existing_req.status == KycStatus.APPROVED:
            raise HTTPException(status_code=400, detail="KYC já aprovado")
        # REJECTED → permite nova tentativa: remove a anterior
        await db.delete(existing_req)
        await db.flush()

    if settings.mock_kyc:
        req = KycRequest(
            user_id=current_user.id,
            document=current_user.document,
            provider="mock",
            provider_request_id=f"mock-{current_user.id}",
            status=KycStatus.APPROVED,
            resolved_at=datetime.utcnow(),
        )
        db.add(req)
        await db.flush()
        current_user.verified = True
        current_user.verified_at = datetime.utcnow()
        return req

    req = KycRequest(
        user_id=current_user.id,
        document=current_user.document,
        provider=body.provider,
        status=KycStatus.PENDING,
    )
    db.add(req)
    await db.flush()

    provider_request_id = await _call_provider(
        req=req,
        selfie_token=body.selfie_token,
        document_front_token=body.document_front_token,
        document_back_token=body.document_back_token,
    )

    req.provider_request_id = provider_request_id
    req.status = KycStatus.IN_REVIEW

    return req


@kyc_router.get("/status", response_model=KycStatusResponse)
async def get_kyc_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retorna o status atual da solicitação de KYC do usuário."""
    result = await db.execute(
        select(KycRequest).where(KycRequest.user_id == current_user.id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Nenhuma solicitação de KYC encontrada")
    return req


@kyc_router.post("/webhook")
async def kyc_webhook(
    payload: KycWebhookPayload,
    x_kyc_signature: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint chamado pelo provider KYC quando a verificação é concluída.
    Valida a assinatura HMAC-SHA256 do webhook antes de processar.
    """
    if settings.kyc_webhook_secret and x_kyc_signature:
        expected = hmac.new(
            settings.kyc_webhook_secret.encode(),
            payload.model_dump_json().encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, x_kyc_signature):
            raise HTTPException(status_code=401, detail="Assinatura do webhook inválida")

    result = await db.execute(
        select(KycRequest).where(
            KycRequest.provider_request_id == payload.request_id
        )
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Solicitação de KYC não encontrada")

    if req.status in (KycStatus.APPROVED, KycStatus.REJECTED):
        return {"status": "already_resolved"}

    now = datetime.utcnow()

    if payload.status.upper() == "APPROVED":
        req.status = KycStatus.APPROVED
        req.resolved_at = now

        user_result = await db.execute(
            select(User).where(User.id == req.user_id)
        )
        user = user_result.scalar_one()
        user.verified = True
        user.verified_at = now

    elif payload.status.upper() == "REJECTED":
        req.status = KycStatus.REJECTED
        req.rejection_reason = payload.rejection_reason
        req.resolved_at = now

    else:
        req.status = KycStatus.IN_REVIEW

    return {"status": "ok", "kyc_status": req.status}


@kyc_router.post("/admin/approve/{user_id}", tags=["admin"])
async def admin_approve_kyc(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Aprovação manual por operador (fallback quando o provider não está integrado).
    Requer autenticação de admin — adicionar middleware de role quando implementar roles.
    """
    result = await db.execute(
        select(KycRequest).where(KycRequest.user_id == user_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Solicitação de KYC não encontrada")

    now = datetime.utcnow()
    req.status = KycStatus.APPROVED
    req.resolved_at = now

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()
    user.verified = True
    user.verified_at = now

    return {"status": "ok", "user_id": user_id, "verified": True}


# ─── Provider integration stub ─────────────────────────────────────────────────

async def _call_provider(
    req: KycRequest,
    selfie_token: str | None,
    document_front_token: str | None,
    document_back_token: str | None,
) -> str:
    """
    Envia os tokens de mídia ao provider KYC e retorna o ID externo da solicitação.

    Adaptar para o provider escolhido:
      - Idwall:  POST https://api.idwall.co/v1/reports  (SDK BR)
      - Unico:   POST https://api.unico.io/...           (SDK BR)
      - Serpro:  GET  https://gateway.apiserpro.serpro.gov.br/consulta-cpf-df/...
      - Persona: POST https://withpersona.com/api/v1/inquiries (internacional)

    Por enquanto retorna um ID fictício — a integração real requer a API key
    do provider configurada via variável de ambiente.
    """
    if not selfie_token or not document_front_token:
        raise HTTPException(
            status_code=400,
            detail="selfie_token e document_front_token são obrigatórios para KYC real. "
                   "Em desenvolvimento, use MOCK_KYC=true."
        )

    return f"{req.provider}-pending-{req.id}"
