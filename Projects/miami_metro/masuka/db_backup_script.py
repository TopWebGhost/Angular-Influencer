from celery.decorators import task
import commands, datetime
from django.utils.encoding import smart_unicode
from django.conf import settings


''' Our DB server on Ec2. This is the elastic IP.'''
DB_SERVER = settings.DATABASES['default']['HOST']


@task(name = "masuka.db_backup_script.use_postgres")
def use_postgres():

    '''
        #### NEW UPDATE::: We're using Heroku postgres now. This is an additional safegaurd for our data.
    '''
    import commands

    cmd = 'heroku pgbackups:capture --app beta-getshelf'
    res = commands.getoutput(cmd)
    print "Taking backup: %s... Result: %s " % (cmd, res)
    return

@task(name = "masuka.db_backup_script.use_aws_s3")
def use_aws_s3():


    

    '''
        We're going to use S3 to store our daily backups.
        ASSUMPTION: This MUST be run from inside the DB server.
    '''
    from boto.s3.connection import S3Connection
    conn = S3Connection(settings.AWS_KEY, settings.AWS_PRIV_KEY)
    bucket = conn.create_bucket('getshelf-db-backup-bucket')
    print "Creating bucked "
    today = datetime.date.today()
    new_key = bucket.new_key('backup-' + today.isoformat())
    print "Created new key: backup-" + today.isoformat()
    log_fname = _create_filename()
    print "Log file " + log_fname
    cmd0 = "sudo -u postgres pg_dump --no-password -Ft devel_db -U postgres > " + log_fname
    print cmd0
    output = commands.getoutput(cmd0)
    print smart_unicode(output)
    gzip_command = "gzip " + log_fname
    print "Zipping it up.."
    commands.getoutput(gzip_command)
    new_key.set_contents_from_filename(log_fname + ".gz")

def _create_filename():
    timestamp = datetime.datetime.now()
    filepath = "/home/ubuntu"
    log_fname = "%s%s%4d%s%02d%s%02d%s%02d%s%02d%s%02d%s" %\
                          (filepath, "/", timestamp.year, "-", timestamp.month, "-", timestamp.day, "-",\
                               timestamp.hour, "-", timestamp.minute, "-", timestamp.second, "-pg.tar")
                          
    return log_fname

def _take_backup(db_server):
    print "DB BACKUP START"
    
    log_fname = _create_filename()
    
    print "Getting database contents into file: " + smart_unicode(log_fname)
    #db_server = "69.120.105.217"
    cmd0 = "/usr/bin/pg_dump --no-password -Ft -h " + db_server + " devel_db -U django_user > " + log_fname
    print cmd0
    output = commands.getoutput(cmd0)
    print smart_unicode(output)
    return log_fname
    
@task(name = "masuka.db_backup_script.execute_sqldump_restore")
def execute_sqldump_restore():
    '''
       1. Get existing database contents into file
       2. Drop backup database
       3. Re-create backup database
       4. 
    '''
    
    log_fname = _take_backup(DB_SERVER)
    
    print "Dropping database: backup_db"
    cmd1 = "/usr/bin/dropdb backup_db -U postgres"
    print cmd1
    output = commands.getoutput(cmd1)
    print smart_unicode(output)
    
    print "Re-creating database: backup_db"
    cmd2 = "/usr/bin/createdb -O django_user backup_db -U postgres"
    print cmd2
    output = commands.getoutput(cmd2)
    print smart_unicode(output)
    
    print "Restoring data to backup_db"
    cmd3 = "/usr/bin/pg_restore --no-owner --dbname=backup_db -U django_user " + log_fname
    print cmd3
    output = commands.getoutput(cmd3)
    print smart_unicode(output)
    

def download_db_backup_from_s3(output_filename):
    """
        Downloads the latest DB snapshot from S3 and stores it in the given filename
        from where the code was executed.
    """
    from boto.s3.connection import S3Connection
    conn = S3Connection(settings.AWS_KEY, settings.AWS_PRIV_KEY)
    bucket = conn.create_bucket('getshelf-db-backup-bucket')
    print "Creating bucked "
    today = datetime.date.today()
    new_key = bucket.new_key('backup-' + today.isoformat())
    new_key.get_contents_to_filename(output_filename)
    print "Done!"
    