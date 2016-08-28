from celery.decorators import task
from debra.models import ProductModel, Brands, ProductPrice, Platform, Posts, UserProfile
import boto
from boto.ec2.connection import EC2Connection
from django.conf import settings
import math
from angel import price_tracker
import datetime
from hanna import blog_content_manager
from django.core.mail import send_mail

# constants
theshelf_key = 'miami'
DEPLOYMENT_SCRIPTS = {'price-tracker': settings.PROJECT_PATH + '/../deployments/price-tracker/user_data.sh',
                      'blog-crawler-daily': settings.PROJECT_PATH + '/../deployments/daily-fetcher/user_data.sh',
                      'blog-crawler-indepth': settings.PROJECT_PATH + '/../deployments/indepth-fetcher/user_data.sh',
                      'blog-importer': settings.PROJECT_PATH + '/../deployments/product-importer-from-blogs/user_data.sh',
                      'platform-post-processing': settings.PROJECT_PATH + '/../deployments/platform-data-postprocessing/user_data.sh',
                      'celery-default': settings.PROJECT_PATH + '/../deployments/celery-default/user_data.sh',
                      'daily-submitter': settings.PROJECT_PATH + '/../deployments/daily-submitter/user_data.sh',
                      'submitter-backup-db': settings.PROJECT_PATH + '/../deployments/db-second/user_data.sh',

}

MAX_EC2_INSTANCES = 20

TASK_TYPES = ['price-tracker',
              'blog-crawler-daily',
              'blog-importer',
              'blog-crawler-indepth',
              'platform-post-processing',
              'celery-default',
              'daily-submitter',
              'submitter-backup-db',
              ]

TASK_THROUGHPUT_PER_MIN = {'price-tracker': 7, 'blog-crawler-daily': 3, 'blog-importer': 3}

INSTANCE_TYPE_PER_TASK = {'price-tracker': 'c3.xlarge',
                          'blog-crawler-daily': 'c3.xlarge',
                          'blog-importer': 'c3.xlarge',
                          'blog-crawler-indepth': 'c3.xlarge',
                          'platform-post-processing': 'c3.xlarge',
                          'celery-default': 'c3.xlarge',
                          'daily-submitter': 'c3.xlarge',
                          'submitter-backup-db': 'c3.xlarge'}

AMI_IDS = {'us-east-1': 'ami-e533308c', 'us-west-2': 'ami-f65d31c6', 'submitter-backup-db': 'ami-b2db7eda'}
AWS_KEYS = {'us-east-1': 'miami', 'us-west-2': 'miami'}

class EC2Manager(object):

    def __init__(self, num_tasks=0, max_hours=0, task_type=None, region='us-east-1'):
        assert task_type in TASK_TYPES
        regions = boto.ec2.regions()
        self.region = region
        self.region_selected = None
        for r in regions:
            if r.name == region:
                self.region_selected = r
                break
        self.conn = EC2Connection(settings.AWS_KEY, settings.AWS_PRIV_KEY, region=self.region_selected)
        ## hack to find the right AMI for submitter-backup-db machine
        my_images = self.conn.get_all_images(owners=['self'], image_ids=[AMI_IDS[region]] if task_type != 'submitter-backup-db' else [AMI_IDS[task_type]])
        assert len(my_images) == 1
        self.ami = my_images[0]
        self.reservation_ids = []
        self.task_type = task_type
        self.instance_type = INSTANCE_TYPE_PER_TASK[self.task_type]
        if num_tasks > 0:
            self.max_instances_needed = self.calculate_num_instances_needed(num_tasks, max_hours)
            if self.max_instances_needed > MAX_EC2_INSTANCES:
                send_mail('Problem with starting price tracker: we need %d instances, quota: %d'% (self.max_instances_needed, MAX_EC2_INSTANCES) , 'Price tracker had problems',
                        'lauren@theshelf.com',
                        ['atul@theshelf.com'], fail_silently=False)
                self.max_instances_needed = MAX_EC2_INSTANCES

    def calculate_num_instances_needed(self, num_tasks, max_hours):
        total_minutes = num_tasks/TASK_THROUGHPUT_PER_MIN[self.task_type]
        total_hours = math.ceil(total_minutes/60.0)
        instances_required = int(math.ceil(total_hours/max_hours))
        return instances_required

    def launch_instances(self, howmany):
        print "Launching %d instances"% howmany
        reservation = self.ami.run(min_count=1,
                                   max_count=howmany,
                                   key_name=AWS_KEYS[self.region],
                                   instance_type=self.instance_type,
                                   instance_initiated_shutdown_behavior='terminate',
                                   user_data=open(DEPLOYMENT_SCRIPTS[self.task_type]).read())

        self.reservation_ids.append(reservation.id)

    def start(self, howmany=None):
        if howmany:
            self.launch_instances(howmany)
        else:
            self.launch_instances(self.max_instances_needed)

    @staticmethod
    def get_instances(reservation_ids, region):
        instances = []
        conn = EC2Connection(aws_access_key_id=settings.AWS_KEY,
                             aws_secret_access_key=settings.AWS_PRIV_KEY,
                             region=region)
        reservations = conn.get_all_reservations()
        for reservation in reservations:
            if reservation.id in reservation_ids:
                print "Checking instances in reservation: %s" % reservation
                for i in reservation.instances:
                    instances.append(i)
        return instances

    @staticmethod
    def check_instances_status(reservation_ids, region):
        instances = EC2Manager.get_instances(reservation_ids, region)
        for i in instances:
            i.update()
            print "Instance %s, current status: %s" % (i.ip_address, i.state)

    @staticmethod
    def terminate_instances(reservation_ids, region):
        assert len(reservation_ids) > 0
        instances = EC2Manager.get_instances(reservation_ids, region)
        for i in instances:
            i.terminate()
            print "Terminated %s, current status: %s" % (i.ip_address, i.state)


@task(name='quinn.manager.terminate', ignore_result=True)
def terminate(reservation_ids=None, region=None):
    '''
    TODO: we should check if there are any pending tasks for the default celery queue
        and send an email to us.
    '''
    EC2Manager.terminate_instances(reservation_ids, region)


##############################################################################
##############################################################################
##################################  PRICE TRACKER ############################
##############################################################################

@task(name="quinn.manager.price_tracker_instance_manager", ignore_result=True)
def price_tracker_instance_manager(max_hours=6, max_items_to_pick=None):
    '''
    Issue celery tasks to price track max_items_to_pick wishlistitems.
    Then run instances to handle this load.
    Then issue another celery task for future to terminate the instances.
    '''
    num_tasks = price_tracker.run_price_updates(max_items_to_pick, True)
    ec2manager = EC2Manager(num_tasks=num_tasks, max_hours=max_hours, task_type='price-tracker', region='us-west-2')
    ec2manager.start()
    terminate.apply_async(args=[ec2manager.reservation_ids, ec2manager.region_selected], countdown=max_hours*60*60)
    return ec2manager




def start_daily_postprocessing_task_submission_instance():
    '''
    This is used to create an EC2 instance that runs second-db instance (this name needs to be updated, we no
    longer create a second db).
    '''
    ec2manager = EC2Manager(task_type='submitter-backup-db')
    ec2manager.launch_instances(1)

