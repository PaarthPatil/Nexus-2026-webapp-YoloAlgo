from fastapi import FastAPI
from detector import get_count

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Backend running"}

@app.get("/count")
def count():
    print("COUNT ENDPOINT HIT")
    return {"box_count": get_count()}
