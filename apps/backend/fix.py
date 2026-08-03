with open("alembic/versions/0001_initial_schema.py", "r") as f:
    content = f.read()
content = content.replace("server_default=sa.text('gen_random_uuid()'), ", "")
content = content.replace("server_default=sa.text(\"gen_random_uuid()\"), ", "")
with open("alembic/versions/0001_initial_schema.py", "w") as f:
    f.write(content)
