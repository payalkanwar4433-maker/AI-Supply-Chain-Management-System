from fastapi import FastAPI
from routers.auth import router as auth_router
from routers.web import router as web_router
from fastapi.staticfiles import StaticFiles

app=FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def home():
    return{"message":"SupplyChainAI is running"}


app.include_router(auth_router)
app.include_router(web_router)