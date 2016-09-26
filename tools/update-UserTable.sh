#!/bin/bash

echo "Backup UserTable..."
cp /opt/docklet/global/sys/UserTable.db /opt/docklet/global/sys/UserTable.db.backup

sed -i "s/^    beans/#    beans/g" ../src/model.py
sed -i "s/^        self.beans/#        self.beans/g" ../src/model.py

echo "Alter UserTable..."
python3 alterUserTable.py

git checkout -- ../

