"""Authenticated API. Tenant and principal come from the server-side token map."""
import secrets
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from whale_core.config import Identity
from whale_core.runtime import build
from whale_core.storage import scoped_id


class Search(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=6, ge=1, le=20)
    rerank: bool = True
    answer: bool = False


class Feedback(BaseModel):
    helpful: bool


def create_app(service=None):
    @asynccontextmanager
    async def lifespan(app):
        if app.state.service is None:
            app.state.service = build()
        yield

    app = FastAPI(title="HuggingWhale Knowledge API", version="2.0.0", lifespan=lifespan)
    app.state.service = service
    bearer = HTTPBearer(auto_error=False)

    def get_service():
        return app.state.service

    def identify(auth: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
                 svc=Depends(get_service)):
        token = auth.credentials if auth else ""
        for item in svc.cfg.api_tokens:
            if secrets.compare_digest(token, item["token"]):
                return Identity(item["tenant"], item["principal"], item.get("admin", False))
        raise HTTPException(401, "Valid bearer token required")

    def admin(identity=Depends(identify)):
        if not identity.admin:
            raise HTTPException(403, "Admin token required")
        return identity

    def safe(call):
        try:
            return call()
        except ValueError as error:
            raise HTTPException(400, str(error)) from None
        except LookupError:
            raise HTTPException(404, "Not found") from None
        except PermissionError:
            raise HTTPException(403, "Forbidden") from None
        except Exception:
            raise HTTPException(503, "Dependency unavailable; check configuration and index readiness") from None

    @app.get("/health")
    def health():
        return {"status": "alive", "version": "2.0.0"}

    @app.get("/identity")
    def who(identity=Depends(identify)):
        return {"tenant": identity.tenant, "principal": identity.principal, "admin": identity.admin}

    @app.get("/ready")
    def ready(identity=Depends(admin), svc=Depends(get_service)):
        def check():
            svc.atlas.db.command("ping")
            svc.objects.client.head_bucket(Bucket=svc.cfg.s3_bucket)
            indexes = [{"name": i["name"], "status": i.get("status"), "queryable": i.get("queryable", False)}
                       for i in svc.atlas.chunks.list_search_indexes()]
            return {"indexes": indexes, "ready": all(any(i["name"] == n and i["queryable"]
                    for i in indexes) for n in ("hw_vector", "hw_keyword"))}
        return safe(check)

    @app.post("/documents", status_code=202)
    def upload(file: UploadFile = File(...), document_id: str = Form(...),
               allowed_principals: str = Form("tenant"), identity=Depends(admin), svc=Depends(get_service)):
        raw = file.file.read(svc.cfg.max_upload_bytes + 1)
        return safe(lambda: svc.submit(identity, document_id, file.filename or "document.txt", raw,
                                        allowed_principals.split(",")))

    @app.get("/documents")
    def documents(identity=Depends(identify), svc=Depends(get_service)):
        return safe(lambda: list(svc.atlas.documents.find({"tenant": identity.tenant, "deleted": False,
            "allowed_principals": {"$in": identity.access}},
            {"_id": 0, "document_id": 1, "filename": 1, "chunk_count": 1,
             "indexed_at": 1, "requested_job": 1}).limit(200)))

    @app.delete("/documents/{document_id}")
    def delete(document_id: str, identity=Depends(admin), svc=Depends(get_service)):
        return safe(lambda: svc.delete(identity, document_id))

    @app.get("/documents/{document_id}/source")
    def source(document_id: str, identity=Depends(identify), svc=Depends(get_service)):
        def read():
            row = svc.atlas.documents.find_one({"_id": scoped_id(identity.tenant, document_id),
                "tenant": identity.tenant, "deleted": False, "allowed_principals": {"$in": identity.access}})
            if not row or not row.get("active_source"):
                raise LookupError()
            # Authenticated proxy, not a public or long-lived presigned URL.
            return Response(svc.objects.get(row["active_source"]), media_type="application/octet-stream",
                            headers={"Content-Disposition": "attachment; filename=source.bin"})
        return safe(read)

    @app.get("/jobs/{job_id}")
    def job(job_id: str, identity=Depends(admin), svc=Depends(get_service)):
        def read():
            row = svc.atlas.jobs.find_one({"_id": job_id, "tenant": identity.tenant},
                {"_id": 0, "state": 1, "attempts": 1, "chunk_count": 1, "error": 1, "document_id": 1})
            if not row:
                raise LookupError()
            return row
        return safe(read)

    @app.post("/search")
    def search(body: Search, identity=Depends(identify), svc=Depends(get_service)):
        return safe(lambda: svc.search(identity, **body.model_dump()))

    @app.post("/feedback/{trace_id}")
    def feedback(trace_id: str, body: Feedback, identity=Depends(identify), svc=Depends(get_service)):
        def write():
            result = svc.atlas.events.update_one({"_id": trace_id, "tenant": identity.tenant,
                "principal": identity.principal}, {"$set": {"helpful": body.helpful}})
            if not result.matched_count:
                raise LookupError()
            return {"status": "recorded"}
        return safe(write)

    return app


app = create_app()
