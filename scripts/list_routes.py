from api.main import app

for route in app.routes:
    methods = ", ".join(route.methods) if hasattr(route, "methods") else "N/A"
    print(f"Path: {route.path:30} Methods: {methods}")
