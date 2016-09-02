#!/bin/bash

PGPASSWORD="pd7llu95ull6g4eqrqvmg70adbo" psql -U uesibiqff80vva -d d3m1pmh4613qg2 -h ec2-54-83-196-213.compute-1.amazonaws.com << EOF
$1
EOF
