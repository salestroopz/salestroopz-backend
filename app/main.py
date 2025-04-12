from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"status": "Salestroopz backend is live!"}
