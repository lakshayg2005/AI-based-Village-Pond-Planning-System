# Add these lines to your existing app/main.py.
# Do not replace your existing authentication/CORS/database setup.

from app.api.routes.catchment import router as catchment_router

# after app = FastAPI(...)
app.include_router(catchment_router)
