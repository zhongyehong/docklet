import sys
sys.path.append("../src/")
from model import db,User

print("Query all users:")
users = User.query.all()
print(users)
newusers = []
print("Copy data to new users and set their beans to 10000...")
for user in users:
    newuser = User(user.username,user.password,user.avatar,user.nickname,user.description,user.status,
                    user.e_mail,user.student_number,user.department,user.truename,user.tel,user.register_date,
                    user.user_group,user.auth_method)
    newuser.beans = 10000
    newusers.append(newuser)
print("Drop all table...")
db.drop_all(bind='__all__')
print("Create all tables with beans...")
setattr(User,'beans',db.Column(db.Integer))
db.create_all(bind='__all__')
for newuser in newusers:
    db.session.add(newuser)
    db.session.commit()
print("Update users table successfully!")
