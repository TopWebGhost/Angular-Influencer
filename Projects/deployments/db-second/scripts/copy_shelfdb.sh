#!/bin/bash

echo "theshelfdbinstance.cydo4oi1ymxb.us-east-1.rds.amazonaws.com:5432:shelfdb:theshelfmaster:messier78_%starbuck" >> ~/.pgpass
echo "127.0.0.1:5432:shelfdb:theshelfmaster:messier78_%starbuck" >> ~/.pgpass
echo "127.0.0.1:5432:template1:theshelfmaster:messier78_%starbuck" >> ~/.pgpass
chmod 600 ~/.pgpass

echo "Dropping old db"
dropdb -w -U theshelfmaster -h 127.0.0.1 shelfdb
echo "Creating new db"
createdb -w -h 127.0.0.1 -U theshelfmaster shelfdb
echo "Done"

cd ~/shelfdb_dump/ && rm -fr ./*
DUMP_ID="shelfdb-$(date '+%Y-%m-%d-%H%M%S')"
echo Dumping to "$DUMP_ID"


echo "$(date) Starting pg_dump"
pg_dump -h theshelfdbinstance.cydo4oi1ymxb.us-east-1.rds.amazonaws.com -Fd -f "$DUMP_ID" -j4 -U theshelfmaster -d shelfdb
echo "$(date) pg_dump finished"

echo "$(date) Starting pg_restore"
pg_restore -h 127.0.0.1 -j8 -U theshelfmaster -d shelfdb "$DUMP_ID"
echo "$(date) pg_restore finished"
