from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import ingredients, recipes, scrape, sites

app = FastAPI(title="Recipe Scraper Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sites.router)
app.include_router(recipes.router)
app.include_router(scrape.router)
app.include_router(ingredients.router)


@app.get("/health")
def health():
    return {"status": "ok"}
