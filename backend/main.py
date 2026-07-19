import os, re, csv, json, asyncio, requests, ipaddress, psutil
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
from database import get_db, engine, Base, AsyncSessionLocal
from models import User, CustomBreach

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DB_FOLDER = "../databases"

@app.get("/api/status")
async def get_server_status():
    return {"cpu": psutil.cpu_percent(interval=0.1)}

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    asyncio.create_task(load_custom_databases())

async def load_custom_databases():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(CustomBreach.source_name).distinct())
        loaded_sources = set(row[0] for row in result.fetchall())
        if not os.path.exists(DB_FOLDER): os.makedirs(DB_FOLDER, exist_ok=True); return
        for filename in os.listdir(DB_FOLDER):
            if filename.endswith(".txt") or filename.endswith(".csv"):
                source_name = filename.replace(".txt", "").replace(".csv", "")
                if source_name not in loaded_sources:
                    filepath = os.path.join(DB_FOLDER, filename)
                    batch = []
                    if filename.endswith(".csv"):
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            first_line = f.readline(); delimiter = ';' if ';' in first_line else ','; f.seek(0)
                            reader = csv.DictReader(f, delimiter=delimiter)
                            for row in reader:
                                clean_row = {k.strip().lower(): v.strip() for k, v in row.items() if k and v}
                                if clean_row: batch.append(CustomBreach(source_name=source_name, line_data=json.dumps(clean_row, ensure_ascii=False)))
                                if len(batch) >= 5000: db.add_all(batch); await db.commit(); batch = []
                    else:
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            for line in f:
                                if line.strip(): batch.append(CustomBreach(source_name=source_name, line_data=line.strip()))
                                if len(batch) >= 5000: db.add_all(batch); await db.commit(); batch = []
                    if batch: db.add_all(batch); await db.commit()

class UserCreate(BaseModel): username: str; email: str | None = None; password: str
class UserLogin(BaseModel): username: str; password: str
class UpgradeRequest(BaseModel): username: str; plan: str
class SearchRequest(BaseModel): query: str; type: str

@app.post("/api/register")
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    if not user.email or not re.match(r"[^@]+@[^@]+\.[^@]+", user.email): raise HTTPException(status_code=400, detail="Invalid email")
    if (await db.execute(select(User).where(User.username == user.username))).scalars().first(): raise HTTPException(status_code=400, detail="User exists")
    db.add(User(username=user.username, email=user.email, hashed_password=pwd_context.hash(user.password), plan="free", credits=100)); await db.commit()
    return {"success": True}

@app.post("/api/login")
async def login(user: UserLogin, db: AsyncSession = Depends(get_db)):
    db_user = (await db.execute(select(User).where(User.username == user.username))).scalars().first()
    if not db_user or not pwd_context.verify(user.password, db_user.hashed_password): raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"success": True, "user": {"username": db_user.username, "plan": db_user.plan, "credits": db_user.credits}}

@app.post("/api/upgrade")
async def upgrade_plan(req: UpgradeRequest, db: AsyncSession = Depends(get_db)):
    db_user = (await db.execute(select(User).where(User.username == req.username))).scalars().first()
    if not db_user: raise HTTPException(status_code=404, detail="Not found")
    if req.plan == "pro": db_user.plan = "pro"; db_user.credits += 1000
    elif req.plan == "ent": db_user.plan = "enterprise"
    await db.commit(); return {"success": True, "plan": db_user.plan, "credits": db_user.credits}

def parse_line(line: str) -> dict:
    data = {}
    if line.startswith("{") and line.endswith("}"): return {k.lower(): str(v) for k, v in json.loads(line).items()}
    if ";" in line:
        for p in line.split(";"):
            if ":" in p: k, v = p.split(":", 1); data[k.strip().lower()] = v.strip()
        return data
    if ":" in line:
        parts = line.split(":", 1); key = parts[0].strip().lower(); val = parts[1].strip() if len(parts) > 1 else ""
        if "@" in key and "." in key: data['email'] = key; data['password'] = val
        else: data['username'] = key; data['password'] = val
        return data
    return {'raw': line}

def matches_search_type(line, query, req_type):
    data = parse_line(line); q = query.lower()
    keys = {'email': ['email', 'mail'], 'username': ['username', 'user', 'login'], 'name': ['name', 'fullname', 'fio'], 'password': ['password', 'pass', 'pwd']}
    for k, v in data.items():
        if k in keys.get(req_type, []) and q in v.lower(): return True
    return False

async def perform_search(query, req_type, db):
    results = []
    if req_type == "ip":
        try:
            ip_res = requests.get(f"https://ipwho.is/{query}/", timeout=5).json()
            if ip_res.get("success"): results.append({"source": "GeoIP", "data": f"IP: {ip_res.get('ip')}\nCountry: {ip_res.get('country')}\nISP: {ip_res.get('connection', {}).get('isp')}"})
        except: pass
    else:
        for row in (await db.execute(select(CustomBreach).where(CustomBreach.line_data.ilike(f"%{query.lower()}%")).limit(1000))).scalars().all():
            if matches_search_type(row.line_data, query, req_type):
                d = parse_line(row.line_data); txt = "\n".join([f"{k.capitalize()}: {v}" for k, v in d.items() if k != 'raw'])
                results.append({"source": row.source_name, "data": txt or d.get('raw', '')})
    return results

@app.post("/api/search")
async def search_api(req: SearchRequest, db: AsyncSession = Depends(get_db)):
    return {"results": await perform_search(req.query.strip(), req.type, db)}

app.mount("/", StaticFiles(directory="../", html=True), name="static")
