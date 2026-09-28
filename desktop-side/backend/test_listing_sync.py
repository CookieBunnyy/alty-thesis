from app.core.database import SessionLocal
from app.services.property_listing_sync import PropertyListingSyncService


db = SessionLocal()

try:
    result = PropertyListingSyncService.sync(db)
    print(result)

finally:
    db.close()