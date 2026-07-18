from sqlalchemy import Column, Integer, String, Text
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    plan = Column(String, default="free")
    credits = Column(Integer, default=100)

class CustomBreach(Base):
    __tablename__ = "custom_breaches"
    
    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String(100))
    line_data = Column(Text)