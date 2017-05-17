#!/usr/bin/python3

import os, json, sys
sys.path.append("../src/")
from model import db, User, UserUsage

def clean_usage(username,alluser=False):
    if alluser:
        usages = UserUsage.query.all()
        for usage in usages:
            usage.cpu = str(0)
            usage.memory = str(0)
            usage.disk = str(0)
        db.session.commit()
    else:
        usage = UserUsage.query.filter_by(username = username).first()
        usage.cpu = str(0)
        usage.memory = str(0)
        usage.disk = str(0)        
        db.session.commit()
    return 

if __name__ == '__main__':
    if len(sys.argv) >= 2:
        username = sys.argv[1]
        clean_usage(username)
    else:
        clean_usage("user",True)
