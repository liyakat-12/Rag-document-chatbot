"""API router aggregation."""

from fastapi import APIRouter

from backend.app.api import admin, chat, documents

api_router = APIRouter()
api_router.include_router(documents.upload_router)
api_router.include_router(documents.router)
api_router.include_router(chat.router)
api_router.include_router(admin.router)

# Required top-level aliases
api_router.add_api_route(
    "/reindex",
    documents.reindex,
    methods=["POST"],
    tags=["documents"],
)
api_router.add_api_route(
    "/documents",
    documents.get_documents,
    methods=["GET"],
    tags=["documents"],
)
api_router.add_api_route(
    "/document/{document_id}",
    documents.remove_document,
    methods=["DELETE"],
    tags=["documents"],
)
