import sqlite3

ORG001 = "19f58b00-b61a-4687-b7b5-1478f392e3f9"
ORG002 = "603af5bf-7fd2-4d0e-b8ca-d2d68c9634d9"

c = sqlite3.connect("data/db.sqlite")
total      = c.execute("SELECT COUNT(*) FROM controls").fetchone()[0]
org1       = c.execute("SELECT COUNT(*) FROM controls WHERE client_org_id = ?", (ORG001,)).fetchone()[0]
org2       = c.execute("SELECT COUNT(*) FROM controls WHERE client_org_id = ?", (ORG002,)).fetchone()[0]
untagged   = c.execute("SELECT COUNT(*) FROM controls WHERE client_org_id IS NULL").fetchone()[0]
docs_org1  = c.execute("SELECT COUNT(DISTINCT document_id) FROM controls WHERE client_org_id = ?", (ORG001,)).fetchone()[0]
c.close()

print(f"total controls    : {total}")
print(f"ORG001 controls   : {org1}  (from {docs_org1} documents)")
print(f"ORG002 controls   : {org2}")
print(f"untagged (NULL)   : {untagged}")