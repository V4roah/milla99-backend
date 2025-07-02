from fastapi import APIRouter, Response
from app.utils.metrics import metrics

router = APIRouter()


@router.get("/metrics", tags=["Monitoring"])
async def get_metrics():
    """
    Endpoint para métricas de Prometheus
    """
    metrics_data = metrics.get_metrics()
    return Response(content=metrics_data, media_type="text/plain")


@router.get("/health", tags=["Monitoring"])
async def health_check():
    """
    Health check simple
    """
    return {
        "status": "healthy",
        "uptime_seconds": metrics.get_metrics().split('\n')[-1].split()[-1]
    }


@router.get("/business-metrics", tags=["Monitoring"])
async def get_business_metrics():
    """
    Métricas específicas de negocio
    """
    return metrics.get_business_metrics()
