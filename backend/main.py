import os
import re
import csv
import json
import asyncio
import requests
import ipaddress
import psutil
from time import time
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

# БЕЗОПАСНОСТЬ: Строгий CORS
origins = [
    "http://localhost",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "http://arcanum.net.swtest.ru",
    "https://arcanum.net.swtest.ru"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# БЕЗОПАСНОСТЬ: Защита от DoS (Rate Limiting)
request_counts = {}
@app.middleware("http")
async def rate_limiter(request: Request, call_next):
    client_ip = request.client.host
    now = time()
    if client_ip in request_counts:
        if now - request_counts[client_ip]['time'] < 10:
            if request_counts[client_ip]['count'] > 30:
                return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})
            request_counts[client_ip]['count'] += 1
        else:
            request_counts[client_ip] = {'time': now, 'count': 1}
    else:
        request_counts[client_ip] = {'time': now, 'count': 1}
    
    response = await call_next(request)
    
    # БЕЗОПАСНОСТЬ: Security Headers
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; connect-src 'self' https://dns.google https://rdap.org https://ipwho.is;"
    return response

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
OSINT_API_KEY = '274fa349-a632-435d-934d-37631b789e84'
OSINT_API_URL = 'https://api.osintcat.net/api/user'
DB_FOLDER = "../databases"

def sanitize_input(text: str) -> str:
    if not text: return text
    text = text.replace("../", "").replace("..\\", "").replace("\x00", "")
    text = re.sub(r'[;|&$<>`\n\r]', '', text)
    return text.strip()

# РЕАЛЬНЫЙ СТАТУС СЕРВЕРА (CPU и PING)
@app.get("/api/status")
async def get_server_status():
    cpu_usage = psutil.cpu_percent(interval=0.1)
    return {"cpu": cpu_usage}

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    asyncio.create_task(load_custom_databases())

# УМНАЯ ЗАГРУЗКА БАЗ (TXT и CSV)
async def load_custom_databases():
    async with AsyncSessionLocal() as db:
        # 1. Получаем список баз, которые УЖЕ загружены в БД
        result = await db.execute(select(CustomBreach.source_name).distinct())
        loaded_sources = set(row[0] for row in result.fetchall())
        
        if not os.path.exists(DB_FOLDER):
            os.makedirs(DB_FOLDER, exist_ok=True)
            return
            
        # 2. Проверяем все файлы в папке
        for filename in os.listdir(DB_FOLDER):
            if filename.endswith(".txt") or filename.endswith(".csv"):
                source_name = filename.replace(".txt", "").replace(".csv", "")
                
                # 3. Если этого файла ЕЩЕ НЕТ в базе - загружаем его!
                if source_name not in loaded_sources:
                    filepath = os.path.join(DB_FOLDER, filename)
                    print(f"\n[ЗАГРУЗКА БАЗЫ] Найден новый файл: {filename}. Начинаю загрузку...")
                    
                    batch = []
                    
                    # --- ОБРАБОТКА CSV (с чтением заголовков) ---
                    if filename.endswith(".csv"):
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            first_line = f.readline()
                            delimiter = ';' if ';' in first_line else ','
                            f.seek(0)
                            reader = csv.DictReader(f, delimiter=delimiter)
                            for row in reader:
                                # Превращаем строку CSV в JSON, чтобы парсер знал где что
                                clean_row = {k.strip().lower(): v.strip() for k, v in row.items() if k and v}
                                if clean_row:
                                    json_line = json.dumps(clean_row, ensure_ascii=False)
                                    batch.append(CustomBreach(source_name=source_name, line_data=json_line))
                                    if len(batch) >= 5000:
                                        db.add_all(batch)
                                        await db.commit()
                                        batch = []
                                        
                    # --- ОБРАБОТКА TXT ---
                    else:
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            for line in f:
                                clean_line = line.strip()
                                if clean_line:
                                    batch.append(CustomBreach(source_name=source_name, line_data=clean_line))
                                    if len(batch) >= 5000:
                                        db.add_all(batch)
                                        await db.commit()
                                        batch = []
                                
                    if batch:
                        db.add_all(batch)
                        await db.commit()
                    print(f"[ЗАГРУЗКА БАЗЫ] Файл {filename} успешно загружен в БД!\n")

class UserCreate(BaseModel):
    username: str
    email: str | None = None
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UpgradeRequest(BaseModel):
    username: str
    plan: str

class SearchRequest(BaseModel):
    query: str
    type: str

@app.post("/api/register")
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    if not user.email or not re.match(r"[^@]+@[^@]+\.[^@]+", user.email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    result = await db.execute(select(User).where(User.username == user.username))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="User already exists")
    hashed_password = pwd_context.hash(user.password)
    db_user = User(username=user.username, email=user.email, hashed_password=hashed_password, plan="free", credits=100)
    db.add(db_user)
    await db.commit()
    return {"success": True, "message": "Registered successfully"}

@app.post("/api/login")
async def login(user: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == user.username))
    db_user = result.scalars().first()
    if not db_user or not pwd_context.verify(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"success": True, "user": {"username": db_user.username, "email": db_user.email, "plan": db_user.plan, "credits": db_user.credits}}

@app.post("/api/upgrade")
async def upgrade_plan(req: UpgradeRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == req.username))
    db_user = result.scalars().first()
    if not db_user: raise HTTPException(status_code=404, detail="User not found")
    if req.plan == "pro":
        db_user.plan = "pro"
        db_user.credits += 1000
    elif req.plan == "ent":
        db_user.plan = "enterprise"
    await db.commit()
    return {"success": True, "plan": db_user.plan, "credits": db_user.credits}

def is_safe_ip(ip_str):
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved: return False
        return True
    except ValueError: return True

# УМНЫЙ ПАРСЕР: Разбирает строку на поля (Словарь)
def parse_line(line: str) -> dict:
    line = line.strip()
    data = {}
    
    # 1. Если это JSON (из CSV)
    if line.startswith("{") and line.endswith("}"):
        try:
            raw = json.loads(line.replace("'", '"'))
            for k, v in raw.items():
                data[k.lower()] = str(v)
            return data
        except: pass
            
    # 2. Если разделитель точка с запятой (key:value;key:value)
    if ";" in line:
        parts = line.split(";")
        for p in parts:
            if ":" in p:
                k, v = p.split(":", 1)
                data[k.strip().lower()] = v.strip()
        if data: return data
            
    # 3. Если стандартное двоеточие (email:pass или login:pass)
    if ":" in line:
        parts = line.split(":", 1)
        key = parts[0].strip().lower()
        val = parts[1].strip() if len(parts) > 1 else ""
        
        known_keys = ['email', 'mail', 'e-mail', 'username', 'user', 'login', 'name', 'fullname', 'fio', 'password', 'pass', 'pwd', 'phone', 'tel', 'ip', 'telegram', 'mcuuid', 'steamid', 'discord']
        if key in known_keys:
            data[key] = val
        else:
            if "@" in key and "." in key:
                data['email'] = key
                data['password'] = val
            else:
                data['username'] = key
                data['password'] = val
        return data
        
    return {'raw': line}

# Форматирование строки для красивого вывода на фронтенд
def format_breach_line(line: str) -> str:
    data = parse_line(line)
    if 'raw' in data and len(data) == 1:
        return data['raw']
        
    parts = []
    order = ['email', 'mail', 'username', 'user', 'login', 'name', 'fullname', 'fio', 'password', 'pass', 'pwd', 'phone', 'ip', 'telegram', 'mcuuid', 'steamid', 'discord']
    
    for k in order:
        if k in data:
            display_name = k.upper() if k in ['ip', 'fio'] else k.capitalize()
            parts.append(f"{display_name}: {data[k]}")
            
    for k, v in data.items():
        if k not in order and k != 'raw':
            parts.append(f"{k.capitalize()}: {v}")
            
    return "\n".join(parts) if parts else line

# СТРОГАЯ ПРОВЕРКА: Ищем только в нужном поле!
def matches_search_type(line: str, query: str, req_type: str) -> bool:
    data = parse_line(line)
    query_lower = query.lower()
    
    keys_to_check = {
        'email': ['email', 'mail', 'e-mail'],
        'username': ['username', 'user', 'login'],
        'name': ['name', 'fullname', 'fio'],
        'password': ['password', 'pass', 'pwd'],
        'phone': ['phone', 'tel', 'mobile'],
        'ip': ['ip', 'ipaddress', 'ip_address'],
        'telegram': ['telegram', 'tg', 'username'],
        'mcuuid': ['mcuuid', 'uuid', 'minecraft_uuid'],
        'steamid': ['steamid', 'steam_id', 'steam'],
        'discord': ['discord', 'discord_id', 'did']
    }
    
    possible_keys = keys_to_check.get(req_type, [req_type])
    
    for k, v in data.items():
        if k in possible_keys:
            if query_lower in v.lower():
                return True
                
    return False

@app.post("/api/search")
async def search_osint(req: SearchRequest, db: AsyncSession = Depends(get_db)):
    query = sanitize_input(req.query)
    req_type = sanitize_input(req.type)
    results = []

    # --- РЕАЛЬНЫЙ ПОИСК ДОМЕНОВ ---
    if req_type == "domain":
        clean_domain = query.replace("https://", "").replace("http://", "").split("/")[0]
        dns_types = {"A": "A", "AAAA": "AAAA", "MX": "MX", "TXT": "TXT", "NS": "NS"}
        for dtype_name, dtype_val in dns_types.items():
            try:
                dns_res = requests.get(f"https://dns.google/resolve?name={clean_domain}&type={dtype_val}", timeout=5).json()
                if dns_res.get("Answer"):
                    records = [f"{ans['name']} -> {ans['data']}" for ans in dns_res["Answer"]]
                    results.append({"source": f"DNS {dtype_name} Records", "data": "\n".join(records)})
            except: pass
        try:
            rdap_res = requests.get(f"https://rdap.org/domain/{clean_domain}", timeout=5).json()
            reg_date = next((e['eventDate'] for e in rdap_res.get('events', []) if e['eventAction'] == 'registration'), 'N/A')
            exp_date = next((e['eventDate'] for e in rdap_res.get('events', []) if e['eventAction'] == 'expiration'), 'N/A')
            registrar = next((e['vcardArray'][1][1][3] for e in rdap_res.get('entities', []) if 'registrar' in e.get('roles', [])), 'N/A')
            statuses = ", ".join(rdap_res.get('status', []))
            results.append({"source": "WHOIS / RDAP", "data": f"Registrar: {registrar}\nCreated: {reg_date}\nExpires: {exp_date}\nStatus: {statuses}"})
        except: pass

    # --- РЕАЛЬНЫЙ ПОИСК IP ---
    elif req_type == "ip":
        if not is_safe_ip(query): raise HTTPException(status_code=400, detail="Security Error: Targeting private/reserved IPs is forbidden")
        try:
            ip_res = requests.get(f"https://ipwho.is/{query}/", timeout=5).json()
            if ip_res.get("success"):
                conn = ip_res.get('connection', {}); tz = ip_res.get('timezone', {})
                geo_data = f"IP: {ip_res.get('ip')}\nType: {ip_res.get('type')}\nCountry: {ip_res.get('country')} ({ip_res.get('country_code')})\nCity: {ip_res.get('city')}\nRegion: {ip_res.get('region')}\nLatitude: {ip_res.get('latitude')}\nLongitude: {ip_res.get('longitude')}\nASN: {conn.get('asn')}\nISP: {conn.get('isp')}\nOrganization: {conn.get('org')}\nDomain: {conn.get('domain')}\nTimezone: {tz.get('id')} (UTC {tz.get('utc_offset')})"
                results.append({"source": "GeoIP & Network Info", "data": geo_data})
        except: pass
        try:
            ptr = ".".join(reversed(query.split("."))) + ".in-addr.arpa"
            dns_res = requests.get(f"https://dns.google/resolve?name={ptr}&type=PTR", timeout=5).json()
            if dns_res.get("Answer"):
                results.append({"source": "Reverse DNS (PTR)", "data": "\n".join([f"{query} -> {ans['data']}" for ans in dns_res["Answer"]])})
        except: pass

    # --- ПОИСК УТЕЧЕК ---
    else:
        query_lower = query.lower()
        sql_query = select(CustomBreach).where(CustomBreach.line_data.ilike(f"%{query_lower}%")).limit(1000)
        result = await db.execute(sql_query)
        local_results = result.scalars().all()
        
        for row in local_results:
            # ПРИМЕНЯЕМ СТРОГУЮ ФИЛЬТРАЦИЮ ПО ТИПУ
            if matches_search_type(row.line_data, query, req_type):
                formatted_data = format_breach_line(row.line_data)
                results.append({"source": row.source_name, "data": formatted_data})

        try:
            headers = {'Authorization': OSINT_API_KEY, 'Content-Type': 'application/json'}
            payload = {"query": req.query, "type": req.type}
            response = requests.post(OSINT_API_URL, headers=headers, json=payload, timeout=5)
            if response.status_code == 200:
                api_data = response.json()
                if api_data.get("results"): results.extend(api_data["results"])
        except: pass

    return {"results": results}

# Раздача статики (HTML, CSS, JS)
app.mount("/", StaticFiles(directory="../", html=True), name="static")