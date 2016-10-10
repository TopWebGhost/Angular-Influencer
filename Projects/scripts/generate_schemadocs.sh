#!/bin/sh

java -jar schemaSpy_5.0.0.jar -t pgsql -db shelfdb -host theshelfdbinstance.cydo4oi1ymxb.us-east-1.rds.amazonaws.com -u theshelfmaster -p messier78_%starbuck -o ./schemadocs -dp postgresql-9.3-1102.jdbc3.jar -s public
