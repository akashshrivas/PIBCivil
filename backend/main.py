from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import articles, health

app = FastAPI(title="UPSCByte API")

# Only needed for requests made FROM THE BROWSER (the search box, the
# ministry filter). Server-to-server fetches -- like the Next.js home
# page rendering on the server -- never hit CORS at all.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000",
    "https://pib-civil.vercel.app"               
                   ],  # add your deployed frontend URL later
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(articles.router)