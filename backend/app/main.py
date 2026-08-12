from fastapi import FastAPI

app=FastAPI()

@app.get("/")
def f():
    return {"message": "Hello World"}
