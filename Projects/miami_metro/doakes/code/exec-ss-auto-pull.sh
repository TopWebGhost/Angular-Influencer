#!/bin/bash 

for i in jcrew express bananarepublic; do
	echo "Executing ruby shopstyle-pull for $i"; 
	ruby /home/kishore/workspace/miami_metro/doakes/code/shopstyle-pull-data-into-db.rb $i ../xml-data/ devel_db
done
