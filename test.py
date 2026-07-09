import os
from dotenv import load_dotenv
from core.memory_store import init_db

load_dotenv()  
print("!")
init_db(os.environ["DATABASE_URL"])
