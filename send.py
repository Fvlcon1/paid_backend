from sqlalchemy import MetaData

# Reflect the database metadata
metadata = MetaData()
metadata.bind = engine

# Recreate the RecentVisit table
Base.metadata.create_all(bind=engine)
print("RecentVisit table has been reinitialized.")
