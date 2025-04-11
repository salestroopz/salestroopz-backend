from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Salestroopz backend is running!"}
