import sqlite3
db = sqlite3.connect("data/db.sqlite")
db.row_factory = sqlite3.Row

def show(title, sql):
    print(f"\n=== {title} ===")
    rows = db.execute(sql).fetchall()
    print("(none)" if not rows else "")
    for r in rows:
        print(dict(r))

show("Organisations", "SELECT id, name, slug FROM client_organizations")
show("Users", "SELECT id, email, client_org_id, role, is_active FROM users")
show("Folder mapping", "SELECT client_org_id, folder_type, folder_path FROM folder_mapping")
show("Tenant mapping", "SELECT client_org_id, tenant_id FROM tenant_mapping")
db.close()