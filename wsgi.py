from app import create_app

# Gunicorn entry point without factory syntax parentheses to avoid start command parsing issues
app = create_app()
