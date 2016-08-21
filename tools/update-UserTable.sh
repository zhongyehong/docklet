#!/bin/bash

echo "Backup UserTable..."
cp /opt/docklet/global/sys/UserTable.db /opt/docklet/global/sys/UserTable.db.backup

sed -i "75s/^ /#/g" ../src/model.py
sed -i "95s/^ /#/g" ../src/model.py

echo "Alter UserTable..."
python3 alterUserTable.py

git checkout -- ../

