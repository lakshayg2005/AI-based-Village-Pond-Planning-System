from fastapi import FastAPI
from .api.routes.catchment import router as catchment_router
from fastapi.middleware.cors import CORSMiddleware
from .api.routes.catchment_v2 import router as catchment_v2_router


app = FastAPI(
    title="The Pond Project API",
    description="Contour-based catchment and pond suitability analysis API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catchment_router)
app.include_router(catchment_v2_router)