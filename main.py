from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from routers.auth import router as auth_router
from routers.web import router as web_router

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def home():
    return RedirectResponse(url="/register", status_code=303)


app.include_router(auth_router)
app.include_router(web_router)
