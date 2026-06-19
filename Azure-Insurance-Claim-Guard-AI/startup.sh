#!/bin/bash
# Azure App Service startup script
# Uses gunicorn (production WSGI server) with uvicorn workers
# Key settings:
#   --workers 1       : Single worker (scale via App Service instances instead)
#   --timeout 120     : Allow 120s for slow SDK initialization
#   --bind 0.0.0.0:8000 : Must match WEBSITES_PORT setting
gunicorn app.main:app \
    --workers 1 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120

