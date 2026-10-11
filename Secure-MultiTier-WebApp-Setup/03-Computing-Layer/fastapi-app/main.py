from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import psycopg2

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "FastAPI is running!"}

@app.get("/messages")
def get_messages():

    connection = psycopg2.connect(
        host="YOUR_PRIVATE_EC2_PRIVATE_IP",
        port=5432,
        database="appdb",
        user="appuser",
        password="apppassword"
    )

    cursor = connection.cursor()

    cursor.execute("SELECT id, message FROM messages ORDER BY id")

    rows = cursor.fetchall()

    cursor.close()
    connection.close()

    return [
        {
            "id": row[0],
            "message": row[1]
        }
        for row in rows
    ]
