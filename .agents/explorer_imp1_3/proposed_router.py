# Registration additions to spoolman/api/v1/router.py

# Import additions around line 18:
from . import export, externaldb, field, filament, models, other, setting, spool, vendor, project, plate, print_job

# Router registration additions around line 106:
app.include_router(project.router)
app.include_router(plate.router)
app.include_router(print_job.router)
