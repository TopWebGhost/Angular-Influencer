su ubuntu -c '/home/ubuntu/Projects/miami_metro/statusapp/run_gunicorn.sh'
su ubuntu -c '/home/ubuntu/Projects/miami_metro/statusapp/run_bookmarklet_test.sh'
su ubuntu -c 'autossh -M 20000 -N -f -i ~/Projects/miami.pem -L 25672:localhost:15672 ubuntu@184.73.153.141'
