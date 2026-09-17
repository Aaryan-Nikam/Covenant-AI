from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import logging

from engine.database.connection import get_db
from engine.gdpr.models import ErasureRequest, PiiDataRecord
from engine.auth.models import Tenant
from engine.dependencies import verify_api_key

logger = logging.getLogger("ironpass.gdpr")
router = APIRouter(prefix="/gdpr", tags=["GDPR"])

@router.get("/data-map")
async def get_data_map(
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
):
    """Get the PII data map for the current tenant."""
    result = await db.execute(
        select(PiiDataRecord)
        .where(PiiDataRecord.tenant_id == tenant.id)
        .order_by(PiiDataRecord.created_at.desc())
        .limit(limit)
    )
    records = result.scalars().all()
    
    # Also get counts by entity type
    counts_result = await db.execute(
        select(PiiDataRecord.entity_type, func.count(PiiDataRecord.id))
        .where(PiiDataRecord.tenant_id == tenant.id)
        .group_by(PiiDataRecord.entity_type)
    )
    counts = [{"type": row[0], "count": row[1]} for row in counts_result]
    
    return {
        "records": records,
        "counts_by_type": counts
    }


@router.get("/erasure-requests")
async def get_erasure_requests(
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """List erasure requests."""
    result = await db.execute(
        select(ErasureRequest)
        .where(ErasureRequest.tenant_id == tenant.id)
        .order_by(ErasureRequest.requested_at.desc())
    )
    return {"requests": result.scalars().all()}


from pydantic import BaseModel

class ErasureRequestBody(BaseModel):
    data_subject_id: str

@router.post("/erasure-requests")
async def create_erasure_request(
    body: ErasureRequestBody,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new erasure request for a data subject and execute the erasure immediately.
    """
    # 1. Null out the PiiDataRecord rows matching data_subject_id and tenant_id
    result = await db.execute(
        update(PiiDataRecord)
        .where(
            PiiDataRecord.tenant_id == tenant.id,
            PiiDataRecord.data_subject_id == body.data_subject_id
        )
        .values(masked_value=None)
    )
    records_deleted = result.rowcount

    # 2. Create the completed ErasureRequest row
    req = ErasureRequest(
        tenant_id=tenant.id,
        data_subject_id=body.data_subject_id,
        status="completed",
        records_deleted=records_deleted,
        completed_at=datetime.now(timezone.utc)
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return {"status": "success", "request_id": str(req.id), "records_deleted": records_deleted}

import io
from fastapi.responses import StreamingResponse

@router.get("/data-map/export")
async def export_data_map(
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Export the Data Map to PDF."""
    result = await db.execute(
        select(
            PiiDataRecord.entity_type,
            func.count(PiiDataRecord.id),
            func.min(PiiDataRecord.created_at),
            func.max(PiiDataRecord.retention_until),
            func.max(PiiDataRecord.legal_basis)
        )
        .where(PiiDataRecord.tenant_id == tenant.id)
        .group_by(PiiDataRecord.entity_type)
    )
    rows = result.all()

    buffer = io.BytesIO()
    
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    # Header
    elements.append(Paragraph("Covenant AI - GDPR Article 30 Data Map", styles['Heading1']))
    elements.append(Paragraph(f"Tenant ID: {tenant.id}", styles['Normal']))
    elements.append(Paragraph(f"Export Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", styles['Normal']))
    elements.append(Spacer(1, 20))

    # Table Data
    data = [["Entity Type", "Record Count", "Oldest Record", "Retention Deadline", "Legal Basis"]]
    for row in rows:
        entity_type, count, oldest, retention, basis = row
        oldest_str = oldest.strftime('%Y-%m-%d') if oldest else "N/A"
        retention_str = retention.strftime('%Y-%m-%d') if retention else "N/A"
        data.append([entity_type, str(count), oldest_str, retention_str, basis or "N/A"])
        
    if len(data) == 1:
        data.append(["No data found", "", "", "", ""])

    t = Table(data, colWidths=[80, 80, 100, 110, 140])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("Generated by Covenant AI — GDPR Article 30 Data Map.", styles['Italic']))

    doc.build(elements)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer, 
        media_type="application/pdf", 
        headers={"Content-Disposition": f"attachment; filename=covenant_gdpr_datamap_{tenant.id}.pdf"}
    )

