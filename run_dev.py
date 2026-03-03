import os
from app.wsgi import app

if __name__ == "__main__":
    # Make sure it binds correctly for WSL access
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    app.run(host=host, port=port)
