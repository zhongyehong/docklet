from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DB_CONNECT_STRING = "sqlite:////opt/docklet/global/sys/UserTable.db"
engine = create_engine(DB_CONNECT_STRING,echo=True)
DB_Session = sessionmaker(bind=engine)
session = DB_Session()
print(session.execute('Select * from User').fetchall())
#print(session.execute('Alter table User add beans integer'))
#print(session.execute('update User set beans=1000'))
print(session.execute('Select * from User').fetchall())

