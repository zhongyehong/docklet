import sys
sys.path.append("../src/")
from model import db,User

users = User.query.all()
db.drop_all(bind='__all__')
print(users)
setattr(User,'beans',db.Column(db.Integer))
db.create_all(bind='__all__')
for user in users:
    newuser = User(user.username,user.password,user.avatar,user.nickname,user.description,user.status,
                    user.e_mail,user.student_number,user.department,user.truename,user.tel,user.register_date,
                    user.user_group,user.auth_method)
    newuser.beans = 1000
    db.session.add(newuser)
    db.session.commit()

