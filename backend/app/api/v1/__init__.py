from fastapi import APIRouter

from app.api.v1 import auth, billing, clients, documents, insights, organizations, portal, whatsapp, work

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(clients.router)
api_router.include_router(documents.router)
api_router.include_router(documents.files_router)
api_router.include_router(work.router)
api_router.include_router(whatsapp.router)
api_router.include_router(whatsapp.webhook_router)
api_router.include_router(billing.router)
api_router.include_router(billing.webhook_router)
api_router.include_router(insights.router)
api_router.include_router(portal.router)
